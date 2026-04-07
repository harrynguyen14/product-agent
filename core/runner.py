from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, AsyncGenerator, Callable, Optional

from actions.action import LLMCallable
from actions.action_graph import ActionGraph, GraphNode
from agents.registry import AgentRegistry, build_default_registry
from config.settings import AppConfig
from core.llm_factory import LLMFactory
from infrastructure.logging import get_logger
from plan.clarify import Clarify
from plan.model import Plan
from plan.planer import Planner
from plan.write_plan import WritePlan
from schemas.agent_result import AgentResult, AgentSuccess
from tools.registry import AbstractToolRegistry, build_default_registry as build_tool_registry

if TYPE_CHECKING:
    from telegram_bot.review_gate import TelegramReviewGate

logger = get_logger("runner")


class EnvironmentRunner:
    """Orchestrates a single pipeline run.

    All collaborators are injected — unit-testable without the full stack (DIP).
    """

    def __init__(
        self,
        config: AppConfig,
        llm: LLMCallable | None = None,
        tool_registry: AbstractToolRegistry | None = None,
        review_gate: Optional["TelegramReviewGate"] = None,
    ) -> None:
        self.config = config
        self._llm: LLMCallable = llm or LLMFactory.build(config)
        self._tool_registry: AbstractToolRegistry = tool_registry or build_tool_registry()
        self._review_gate = review_gate

        stats = self._tool_registry.stats()
        logger.info(
            "runner_init",
            provider=config.llm_provider.value,
            model=config.get_active_model(),
            tools=stats["tools"]["count"],
            skills=stats["skills"]["count"],
            mcp=stats["mcp"]["count"],
        )

    # ------------------------------------------------------------------
    # Builders (private — each has one job)
    # ------------------------------------------------------------------

    def _build_planner(
        self,
        on_plan_ready: Optional[Callable[[str], Any]] = None,
    ) -> Planner:
        write_plan = WritePlan()
        write_plan.set_llm(self._llm)

        clarify = Clarify()
        clarify.set_llm(self._llm)

        return Planner(
            write_plan=write_plan,
            clarify=clarify,
            tool_registry=self._tool_registry,
            max_tasks=7,
            max_retries=self.config.max_retries,
            review_gate=self._review_gate,
            on_plan_ready=on_plan_ready,
        )

    def _build_agent_registry(self, goal: str) -> AgentRegistry:
        return build_default_registry(
            llm=self._llm,
            tools=self._tool_registry.all_tools(),
            goal=goal,
        )

    def _build_action_graph(self, plan: Plan, registry: AgentRegistry) -> ActionGraph:
        graph = ActionGraph()
        for task in plan._tasks:
            task_dict = task.to_dict()

            async def _node_fn(upstream: dict, _task: dict = task_dict) -> AgentResult:
                return await registry.run_task(_task, upstream)

            graph.add_node(GraphNode(
                node_id=task.task_id,
                fn=_node_fn,
                dependent_ids=list(task.dependent_task_ids),
            ))
        return graph

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, problem: str) -> dict[str, Any]:
        logger.info("pipeline_start", problem=problem[:100])

        planner = self._build_planner()
        plan = await planner.run(problem)
        logger.info("plan_accepted", tasks=len(plan))

        registry = self._build_agent_registry(problem)
        graph = self._build_action_graph(plan, registry)

        logger.info("execution_start")
        results: dict[str, AgentResult] = await graph.run()

        success = all(isinstance(r, AgentSuccess) for r in results.values())
        logger.info("execution_done", total=len(results), success=success)

        return {
            "plan": plan,
            "results": {tid: r.output for tid, r in results.items()},
            "success": success,
            "user_problem": problem,
            "report_output": self._extract_report(results),
        }

    async def stream(
        self, problem: str, desired_output: str = ""
    ) -> AsyncGenerator[dict, None]:
        logger.info("pipeline_start", problem=problem[:100])
        yield {"type": "role_start", "role": "ClarifyAgent"}

        # plan_ready_queue lets the planner push the plan text to the stream
        # *before* AskReview blocks waiting for the user's reply.
        plan_ready_queue: asyncio.Queue[str] = asyncio.Queue()

        async def _on_plan_ready(formatted: str) -> None:
            await plan_ready_queue.put(formatted)

        planner = self._build_planner(on_plan_ready=_on_plan_ready)

        logger.info("clarify_start")
        yield {"type": "role_start", "role": "PlanAgent"}

        # Run planner as a background task so we can yield plan_ready
        # events while it is still blocked on AskReview.
        planner_task = asyncio.create_task(planner.run(problem))

        # Yield plan_ready as soon as the planner pushes it (before confirm)
        plan_text = await plan_ready_queue.get()
        yield {"type": "plan_ready", "plan": plan_text}
        yield {"type": "role_end", "role": "PlanAgent", "msg": None}

        # Now wait for the planner to finish (user confirmed or retried)
        plan = await planner_task
        logger.info("plan_accepted", tasks=len(plan))
        for t in plan._tasks:
            logger.info("  task", id=t.task_id, type=t.task_type,
                        instruction=(t.instruction or "")[:60])

        registry = self._build_agent_registry(problem)
        graph = self._build_action_graph(plan, registry)

        for task in plan._tasks:
            yield {"type": "role_start", "role": task.task_type}

        logger.info("execution_start", tasks=len(plan))
        results: dict[str, AgentResult] = await graph.run()

        for tid, r in results.items():
            status = "ok" if isinstance(r, AgentSuccess) else f"FAIL({r.error[:60]})"
            logger.info("  task_done", id=tid, type=r.task_type, status=status)

        success = all(isinstance(r, AgentSuccess) for r in results.values())
        logger.info("execution_done", total=len(results), success=success)

        final_state = {
            "plan": plan,
            "user_problem": problem,
            "report_output": self._extract_report(results),
            "results": {tid: r.output for tid, r in results.items()},
        }
        yield {"type": "done", "state": final_state, "memory": []}

    async def stream_resume(
        self, env: Any, user_reply: str
    ) -> AsyncGenerator[dict, None]:
        if env is None:
            return
        problem = getattr(env, "problem", str(user_reply))
        async for event in self.stream(problem):
            yield event

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_report(results: dict[str, AgentResult]) -> Any:
        for result in reversed(list(results.values())):
            if result.task_type == "report" and isinstance(result, AgentSuccess):
                return result.output
        if results:
            return list(results.values())[-1].output
        return None

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Awaitable, Callable, Optional

from actions.action import ActionContext, LLMAction
from agents.inventory_agent import InventoryAgent
from infrastructure.logging import get_logger
from plan.ask_review import AskReview
from plan.model import Plan
from plan.plan_parser import update_plan_from_rsp
from plan.plan_validator import PlanValidator
from plan.write_plan import WritePlan
from tools.registry import ToolRegistry

if TYPE_CHECKING:
    from telegram_bot.review_gate import TelegramReviewGate

logger = get_logger("planner")

# ---------------------------------------------------------------------------
# Context template (unchanged — passed to WritePlan)
# ---------------------------------------------------------------------------

STRUCTURAL_CONTEXT = """\
## User Requirement
{user_requirement}

## Conversation History
{history}

## Available Components
{inventory}

## Current Plan
{tasks}
"""

# ---------------------------------------------------------------------------
# ReAct prompts for the Planner's internal reasoning loop
# ---------------------------------------------------------------------------

_REACT_THINK_PROMPT = """\
## Goal
{goal}

## Available Components
{inventory}

## Trajectory so far
{trajectory}

Think step-by-step about what kind of plan is needed.
Consider: task types required, which tools/skills are available, parallelism opportunities,
dependencies, and potential failure points.

Output exactly:
  Thought: <your reasoning>
  Conclusion: <one-sentence summary of the plan strategy>
"""

_REACT_OBSERVE_PROMPT = """\
## Goal
{goal}

## Plan that was just rejected or failed validation
{plan}

## Error / User Feedback
{feedback}

## Trajectory so far
{trajectory}

Reason about what went wrong and how to fix it.

Output exactly:
  Thought: <analysis of the problem>
  Fix: <specific change needed in the next plan attempt>
"""


# ---------------------------------------------------------------------------
# Internal ReAct trajectory entry
# ---------------------------------------------------------------------------

class _ThoughtEntry:
    def __init__(self, kind: str, thought: str, conclusion: str = "") -> None:
        self.kind = kind          # "think" | "observe"
        self.thought = thought
        self.conclusion = conclusion

    def to_str(self) -> str:
        lines = [f"[{self.kind.upper()}] Thought: {self.thought}"]
        if self.conclusion:
            lines.append(f"  → {self.conclusion}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

class Planner:
    """Orchestrates clarification → plan generation → user review.

    ReAct integration
    -----------------
    Two reasoning steps have been added around WritePlan:

    1. **Pre-plan Thought** (`_react_think`):
       Before the first WritePlan call, the LLM reasons about the goal,
       available inventory, and plan strategy.  The conclusion is prepended
       to the WritePlan context so the LLM produces a more targeted plan.

    2. **Post-failure Observation** (`_react_observe`):
       After a plan fails validation *or* is rejected by the user, the LLM
       reasons about what went wrong.  The resulting fix-instruction is
       appended to the conversation history, giving WritePlan concrete
       guidance on the next attempt.

    Each concern lives in its own collaborator:
    - WritePlan    : LLM plan generation
    - Clarify      : requirement clarification
    - PlanValidator: validation logic
    - AskReview    : user interaction
    - InventoryAgent: tool/skill scanning
    """

    def __init__(
        self,
        write_plan: WritePlan,
        clarify: Optional[LLMAction] = None,
        tool_registry: Optional[ToolRegistry] = None,
        max_tasks: int = 7,
        max_retries: int = 3,
        review_gate: Optional["TelegramReviewGate"] = None,
        react_llm: Optional[LLMAction] = None,
        on_plan_ready: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> None:
        self.write_plan = write_plan
        self.clarify = clarify
        self.tool_registry = tool_registry
        self.max_tasks = max_tasks
        self.max_retries = max_retries
        self._review_gate = review_gate
        self._react_llm: Optional[LLMAction] = react_llm
        self._on_plan_ready: Optional[Callable[[str], Awaitable[None]]] = on_plan_ready
        self._validator = PlanValidator()

        self._goal: str = ""
        self._plan: Plan = Plan()
        self._history: list[str] = []
        self._inventory_ctx: str = ""
        self._react_trajectory: list[_ThoughtEntry] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, goal: str) -> Plan:
        self._goal = goal
        self._history.clear()
        self._react_trajectory.clear()
        self._history.append(f"User: {goal}")

        if self.tool_registry:
            report = InventoryAgent(self.tool_registry).check(goal)
            self._inventory_ctx = report.context_str()
            self._history.append(f"System (inventory):\n{self._inventory_ctx}")
            logger.info(
                "inventory_check",
                total=report.stats["total"],
                relevant_tools=report.relevant_tools,
                relevant_skills=report.relevant_skills,
                relevant_mcp=report.relevant_mcp,
            )

        if self.clarify:
            logger.info("clarify_start")
            await self._run_clarify()
            logger.info("clarify_done")

        # ReAct step 1 — reason about the goal before writing any plan
        await self._react_think()

        await self._plan_loop()
        return self._plan

    # ------------------------------------------------------------------
    # Clarification
    # ------------------------------------------------------------------

    async def _run_clarify(self) -> None:
        ctx: ActionContext = {"input": self._goal, "config": {}}
        clarified = await self.clarify.run(ctx)
        self._history.append(clarified)

    # ------------------------------------------------------------------
    # ReAct — pre-plan Thought
    # ------------------------------------------------------------------

    async def _react_think(self) -> None:
        """Reason about goal + inventory before writing the plan."""
        llm = self._get_react_llm()
        if llm is None:
            return

        trajectory_str = self._format_react_trajectory() or "(none yet)"
        prompt = _REACT_THINK_PROMPT.format(
            goal=self._goal,
            inventory=self._inventory_ctx or "(no registry)",
            trajectory=trajectory_str,
        )
        try:
            raw = await llm.aask(prompt)
            thought, conclusion = self._parse_think(raw)
            entry = _ThoughtEntry("think", thought, conclusion)
            self._react_trajectory.append(entry)
            self._history.append(f"System (ReAct think):\n{entry.to_str()}")
            logger.info("react_think", thought=thought[:120], conclusion=conclusion[:80])
        except Exception as e:
            logger.warning("react_think_failed", error=str(e))

    # ------------------------------------------------------------------
    # ReAct — post-failure Observation
    # ------------------------------------------------------------------

    async def _react_observe(self, plan_str: str, feedback: str) -> None:
        """Reason about what went wrong after a plan failure or rejection."""
        llm = self._get_react_llm()
        if llm is None:
            return

        trajectory_str = self._format_react_trajectory() or "(none yet)"
        prompt = _REACT_OBSERVE_PROMPT.format(
            goal=self._goal,
            plan=plan_str,
            feedback=feedback,
            trajectory=trajectory_str,
        )
        try:
            raw = await llm.aask(prompt)
            thought, fix = self._parse_observe(raw)
            entry = _ThoughtEntry("observe", thought, fix)
            self._react_trajectory.append(entry)
            self._history.append(
                f"System (ReAct observe):\nThought: {thought}\nFix: {fix}"
            )
            logger.info("react_observe", thought=thought[:120], fix=fix[:80])
        except Exception as e:
            logger.warning("react_observe_failed", error=str(e))

    # ------------------------------------------------------------------
    # Plan generation loop
    # ------------------------------------------------------------------

    async def _plan_loop(self) -> None:
        retries_left = self.max_retries
        attempt = 0
        last_rsp: str = ""

        while True:
            attempt += 1
            logger.info("write_plan_attempt", attempt=attempt)

            ctx: ActionContext = {
                "input": self._build_context_str(),
                "config": {"max_tasks": self.max_tasks},
            }

            rsp = await self.write_plan.run(ctx)
            last_rsp = rsp
            self._history.append(f"Assistant (plan): {rsp}")

            is_valid, error = self._validator.validate(rsp, self._plan)
            if not is_valid:
                logger.warning("plan_invalid", error=str(error), retries_left=retries_left)
                if retries_left > 0:
                    retries_left -= 1
                    # ReAct step 2a — observe validation failure
                    await self._react_observe(rsp, f"Validation error: {error}")
                    self._history.append(f"System: Plan invalid: {error}. Regenerating.")
                    continue
                raise RuntimeError(f"Plan generation failed after retries: {error}")

            retries_left = self.max_retries
            logger.info("plan_generated_ok")

            formatted = self._format_plan(rsp)
            # Notify caller BEFORE blocking on AskReview — lets the bot send
            # the plan to Telegram while the gate is still open for a reply.
            if self._on_plan_ready:
                await self._on_plan_ready(formatted)

            review, confirmed = await AskReview(self._review_gate).run(formatted)
            self._history.append(f"User: {review}")

            if confirmed:
                update_plan_from_rsp(rsp, self._plan)
                logger.info("plan_confirmed", tasks=len(self._plan))
                return

            # ReAct step 2b — observe user rejection
            logger.info("plan_rejected_replanning", feedback=review[:80])
            await self._react_observe(rsp, f"User feedback: {review}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_context_str(self) -> str:
        tasks_json = json.dumps(self._plan.to_list(), indent=2, ensure_ascii=False)
        return STRUCTURAL_CONTEXT.format(
            user_requirement=self._goal,
            history="\n".join(self._history),
            inventory=self._inventory_ctx or "(no registry provided)",
            tasks=tasks_json if self._plan.to_list() else "(none yet)",
        )

    def _get_react_llm(self) -> Optional[LLMAction]:
        """Return the ReAct LLM — either injected or borrowed from write_plan."""
        if self._react_llm is not None:
            return self._react_llm
        # write_plan is an LLMAction — reuse it if it has an LLM set
        if hasattr(self.write_plan, "_llm") and self.write_plan._llm is not None:
            return self.write_plan
        return None

    def _format_react_trajectory(self) -> str:
        return "\n\n".join(e.to_str() for e in self._react_trajectory)

    @staticmethod
    def _parse_think(raw: str) -> tuple[str, str]:
        """Extract Thought and Conclusion from pre-plan think response."""
        thought = ""
        conclusion = ""
        for line in raw.splitlines():
            s = line.strip()
            if s.startswith("Thought:"):
                thought = s[len("Thought:"):].strip()
            elif s.startswith("Conclusion:"):
                conclusion = s[len("Conclusion:"):].strip()
        return thought or raw.strip(), conclusion

    @staticmethod
    def _parse_observe(raw: str) -> tuple[str, str]:
        """Extract Thought and Fix from post-failure observe response."""
        thought = ""
        fix = ""
        for line in raw.splitlines():
            s = line.strip()
            if s.startswith("Thought:"):
                thought = s[len("Thought:"):].strip()
            elif s.startswith("Fix:"):
                fix = s[len("Fix:"):].strip()
        return thought or raw.strip(), fix

    @staticmethod
    def _format_plan(rsp: str) -> str:
        try:
            tasks = json.loads(rsp)
            lines = []
            for t in tasks:
                deps = ", ".join(t.get("dependent_task_ids") or []) or "—"
                lines.append(
                    f"  [{t['task_id']}] ({t['task_type']}) {t['instruction']}  (depends on: {deps})"
                )
            return "\n".join(lines)
        except Exception:
            return rsp

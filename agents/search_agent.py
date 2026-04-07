from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from actions.action import LLMAction
from actions.react_loop import ReActLoop
from agents.base import BaseAgent
from infrastructure.logging import get_logger
from plan.task import TaskType
from schemas.agent_result import AgentResult, fail, ok

logger = get_logger("search_agent")

_BASE_SYSTEM = """\
You are a research search agent operating in a ReAct loop.
Use the available tools iteratively to gather comprehensive, accurate information.
Reason about result quality at each step — if results are vague or incomplete,
refine your query and search again before declaring a Final Answer.

IMPORTANT RULES:
- You MUST call at least one tool before emitting a Final Answer.
- Never answer from internal knowledge alone — always search first.
- If the first search returns poor results, refine and search again.
"""

# Default cap; callers can override via SearchAgent(max_react_steps=N).
# 8 steps allows 3-4 search queries with thinking steps between each,
# which is the minimum needed for multi-angle research topics.
_DEFAULT_MAX_STEPS = 8


class SearchAgent(BaseAgent):
    skill_file: str = "search_skill.md"
    tools: list[BaseTool] = []
    max_react_steps: int = _DEFAULT_MAX_STEPS

    async def run(self, task: dict, upstream: dict[str, Any]) -> AgentResult:
        instruction = task.get("instruction", "")
        task_id = task.get("task_id", "")

        if not self.tools:
            return fail(self.name, task_id, TaskType.search, "No tools registered")

        upstream_str = (
            "\n".join(f"[{k}]: {v}" for k, v in upstream.items()) if upstream else ""
        )

        action = self._make_action(LLMAction)
        loop = ReActLoop(
            action=action,
            tools=self.tools,
            max_steps=self.max_react_steps,
            system_msg=self._get_system(_BASE_SYSTEM),
        )

        try:
            result = await loop.run(goal=instruction, context=upstream_str)
            actions = loop.actions_taken()
            logger.info(
                "search_react_done",
                task_id=task_id,
                steps=result.steps,
                stopped_by=result.stopped_by,
                actions=actions,
            )
            if not actions:
                logger.warning(
                    "search_no_tool_called",
                    task_id=task_id,
                    instruction=instruction[:80],
                )
                return fail(
                    self.name,
                    task_id,
                    TaskType.search,
                    "SearchAgent answered without calling any tool. "
                    "Retry with a more specific instruction.",
                    output=result.answer,
                )
            return ok(self.name, task_id, TaskType.search, result.answer)
        except Exception as e:
            return fail(self.name, task_id, TaskType.search, str(e))

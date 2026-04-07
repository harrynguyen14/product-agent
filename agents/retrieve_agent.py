from __future__ import annotations

from typing import Any, Callable

from langchain_core.tools import BaseTool, StructuredTool

from actions.action import LLMAction
from actions.react_loop import ReActLoop
from agents.base import BaseAgent
from infrastructure.logging import get_logger
from plan.task import TaskType
from schemas.agent_result import AgentResult, fail, ok

logger = get_logger("retrieve_agent")

_BASE_SYSTEM = """\
You are a retrieval agent operating in a ReAct loop.
Use the retrieve tool iteratively to find the most relevant documents.
After each retrieval, reason about result quality:
- If scores are low (< 0.6) or content is off-topic, reformulate the query and retrieve again.
- If results are relevant and sufficient, emit a Final Answer summarising the key retrieved content.
"""

_DEFAULT_MAX_STEPS = 3  # retrieval loops are cheaper — fewer steps needed


def _make_retrieve_tool(retrieve_fn: Callable[[str, int], list[dict]]) -> BaseTool:
    """Wrap a retrieve_fn as a BaseTool so ReActLoop can call it."""

    async def _run(query: str) -> str:
        docs = retrieve_fn(query, 8)
        if not docs:
            return "No documents found."
        return "\n\n".join(
            f"[{i + 1}] (score={d.get('score', 0):.2f}) {d.get('content', '')}"
            for i, d in enumerate(docs)
        )

    return StructuredTool.from_function(
        coroutine=_run,
        name="retrieve",
        description=(
            "Query the knowledge base for relevant documents. "
            "Arg: a natural-language query string. "
            "Returns ranked document chunks with relevance scores."
        ),
    )


class RetrieveAgent(BaseAgent):
    """Retrieves information via an injected retrieve_fn using a ReAct loop.

    The ReAct loop allows the agent to reformulate its query when initial
    results have low relevance scores, rather than returning poor results
    on the first attempt.

    If no retrieve_fn is injected, falls back to a single LLM-based retrieval.
    """

    skill_file: str = "retrieve_skill.md"
    retrieve_fn: Callable[[str, int], list[dict]] | None = None
    max_react_steps: int = _DEFAULT_MAX_STEPS

    async def run(self, task: dict, upstream: dict[str, Any]) -> AgentResult:
        instruction = task.get("instruction", "")
        task_id = task.get("task_id", "")

        # --- ReAct path: retrieve_fn available ---
        if self.retrieve_fn is not None:
            retrieve_tool = _make_retrieve_tool(self.retrieve_fn)
            upstream_str = (
                "\n".join(f"[{k}]: {v}" for k, v in upstream.items()) if upstream else ""
            )

            action = self._make_action(LLMAction)
            loop = ReActLoop(
                action=action,
                tools=[retrieve_tool],
                max_steps=self.max_react_steps,
                system_msg=self._get_system(_BASE_SYSTEM),
            )

            try:
                result = await loop.run(goal=instruction, context=upstream_str)
                logger.info(
                    "retrieve_react_done",
                    task_id=task_id,
                    steps=result.steps,
                    stopped_by=result.stopped_by,
                    queries=[arg for _, arg in loop.actions_taken()],
                )
                return ok(self.name, task_id, TaskType.retrieve, result.answer)
            except Exception as e:
                return fail(self.name, task_id, TaskType.retrieve, str(e))

        # --- Fallback: no retrieve_fn — single LLM call ---
        upstream_str = (
            "\n".join(f"[{k}]: {v}" for k, v in upstream.items()) if upstream else "none"
        )
        action = self._make_action(LLMAction)
        try:
            result = await action.aask(
                f"## Task\n{instruction}\n\n## Context\n{upstream_str}\n\n"
                "Retrieve relevant information to fulfill this task.",
                system_msg=self._get_system(_BASE_SYSTEM),
            )
            return ok(self.name, task_id, TaskType.retrieve, result)
        except Exception as e:
            return fail(self.name, task_id, TaskType.retrieve, str(e))

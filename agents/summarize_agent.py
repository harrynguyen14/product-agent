from __future__ import annotations

from typing import Any

from actions.action import LLMAction
from agents.base import BaseAgent
from plan.task import TaskType
from schemas.agent_result import AgentResult, fail, ok


_BASE_SYSTEM = "You are a summarization agent. Write concise summaries that capture essential information. Preserve key facts, figures, and conclusions."

PROMPT = """\
## Task
{instruction}

## Content to Summarize
{upstream}

Write a concise summary that captures the essential information. Preserve key facts, figures, and conclusions.
"""


class SummarizeAgent(BaseAgent):
    # writing_skill.md consumes the output of this agent to produce the final user report
    skill_file: str = "writing_skill.md"

    async def run(self, task: dict, upstream: dict[str, Any]) -> AgentResult:
        instruction = task.get("instruction", "")
        task_id = task.get("task_id", "")
        upstream_str = (
            "\n\n".join(f"[{k}]:\n{v}" for k, v in upstream.items())
            if upstream else "(no content)"
        )

        action = self._make_action(LLMAction)
        try:
            result = await action.aask(
                PROMPT.format(instruction=instruction, upstream=upstream_str),
                system_msg=self._get_system(_BASE_SYSTEM),
            )
            return ok(self.name, task_id, TaskType.summarize, result)
        except Exception as e:
            return fail(self.name, task_id, TaskType.summarize, str(e))

from __future__ import annotations

from typing import Any

from actions.action import LLMAction
from agents.base import BaseAgent
from plan.task import TaskType
from schemas.agent_result import AgentResult, fail, ok


_BASE_SYSTEM = "You are a precise content extraction agent. Read provided content and extract only what is relevant to the task. Preserve all facts and figures verbatim."

PROMPT = """\
## Task
{instruction}

## Content to Read
{content}

Read and extract the key information relevant to the task. Be precise, preserve facts and figures.
"""


class ReadAgent(BaseAgent):
    skill_file: str = "read_skill.md"

    async def run(self, task: dict, upstream: dict[str, Any]) -> AgentResult:
        instruction = task.get("instruction", "")
        task_id = task.get("task_id", "")
        content = "\n\n".join(str(v) for v in upstream.values()) if upstream else ""

        action = self._make_action(LLMAction)
        try:
            result = await action.aask(
                PROMPT.format(instruction=instruction, content=content or "(no content provided)"),
                system_msg=self._get_system(_BASE_SYSTEM),
            )
            return ok(self.name, task_id, TaskType.read, result)
        except Exception as e:
            return fail(self.name, task_id, TaskType.read, str(e))

from __future__ import annotations

import json
from typing import Any

from actions.action import LLMAction
from agents.base import BaseAgent
from plan.task import TaskType
from schemas.agent_result import AgentResult, fail, ok
from utils.response_parser import ResponseParser


_BASE_SYSTEM = "You are a task decomposition agent. Break complex tasks into smaller, executable subtasks."

PROMPT = """\
## Task to Decompose
{instruction}

## Context
{upstream}

Break this task into 2-5 concrete, executable subtasks. Each subtask must be atomic and independently actionable.

Respond with JSON:
```json
[
  {{"task_id": "1", "instruction": "...", "task_type": "search|retrieve|read|analyze|synthesize|summarize|report|validate"}}
]
```
"""


class DecomposeAgent(BaseAgent):
    skill_file: str = "decompose_skill.md"

    async def run(self, task: dict, upstream: dict[str, Any]) -> AgentResult:
        instruction = task.get("instruction", "")
        task_id = task.get("task_id", "")
        upstream_str = "\n".join(f"[{k}]: {v}" for k, v in upstream.items()) if upstream else "none"

        action = self._make_action(LLMAction)
        raw = await action.aask(
            PROMPT.format(instruction=instruction, upstream=upstream_str),
            system_msg=self._get_system(_BASE_SYSTEM),
        )

        try:
            subtasks = json.loads(ResponseParser.parse_json(raw))
            return ok(self.name, task_id, TaskType.decompose, subtasks)
        except Exception as e:
            return fail(self.name, task_id, TaskType.decompose, str(e), output=raw)

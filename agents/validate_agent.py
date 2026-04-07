from __future__ import annotations

import json
from typing import Any

from actions.action import LLMAction
from agents.base import BaseAgent
from plan.task import TaskType
from schemas.agent_result import AgentResult, fail, ok
from utils.response_parser import ResponseParser


_BASE_SYSTEM = "You are a quality validation agent. Evaluate output strictly against the task requirement."

PROMPT = """\
## Task Instruction
{instruction}

## Output to Validate
{output}

Evaluate whether the output fulfills the task. Respond with JSON:
```json
{{
  "status": "PASS" or "FAIL",
  "issues": ["specific issue if any"],
  "suggested_fix": "actionable fix if FAIL, else empty string"
}}
```
"""


class ValidateAgent(BaseAgent):
    skill_file: str = "validate_skill.md"

    async def run(self, task: dict, upstream: dict[str, Any]) -> AgentResult:
        instruction = task.get("instruction", "")
        task_id = task.get("task_id", "")
        output_to_validate = "\n\n".join(str(v) for v in upstream.values()) if upstream else ""

        action = self._make_action(LLMAction)
        try:
            raw = await action.aask(
                PROMPT.format(instruction=instruction, output=output_to_validate),
                system_msg=self._get_system(_BASE_SYSTEM),
            )
            data = json.loads(ResponseParser.parse_json(raw))
            status = data.get("status", "PASS")
            if status == "PASS":
                return ok(self.name, task_id, TaskType.validate, data)
            return fail(
                self.name, task_id, TaskType.validate,
                error="; ".join(data.get("issues", [])),
                output=data,
            )
        except Exception as e:
            return fail(self.name, task_id, TaskType.validate, str(e))

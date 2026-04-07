from __future__ import annotations

from typing import Any

from actions.action import LLMAction
from actions.action_node import ActionNode
from agents.base import BaseAgent
from plan.task import TaskType
from schemas.agent_result import AgentResult, fail, ok
from schemas.synthesis import SynthesisOutput


_BASE_SYSTEM = "You are a knowledge synthesis agent. Combine multiple sources into a unified, coherent result. Never invent facts."

PROMPT = """\
## Task
{instruction}

## Sources to Synthesize
{upstream}

Synthesize the sources above into a unified result. Resolve contradictions, identify consensus, and highlight remaining uncertainties.
"""


class SynthesizeAgent(BaseAgent):
    skill_file: str = "synthesize_skill.md"

    async def run(self, task: dict, upstream: dict[str, Any]) -> AgentResult:
        instruction = task.get("instruction", "")
        task_id = task.get("task_id", "")
        upstream_str = (
            "\n\n---\n\n".join(f"Source [{k}]:\n{v}" for k, v in upstream.items())
            if upstream else "(no sources)"
        )

        if not upstream:
            return fail(
                self.name, task_id, TaskType.synthesize,
                "No upstream sources to synthesize. Ensure at least one search or analyze task runs first.",
            )

        action = self._make_action(LLMAction)
        node = ActionNode(name=self.name, schema_cls=SynthesisOutput)
        node.set_action(action)

        try:
            result = await node.run(
                PROMPT.format(instruction=instruction, upstream=upstream_str),
                system_msg=self._get_system(_BASE_SYSTEM),
            )
            return ok(self.name, task_id, TaskType.synthesize, result)
        except Exception as e:
            return fail(self.name, task_id, TaskType.synthesize, str(e))

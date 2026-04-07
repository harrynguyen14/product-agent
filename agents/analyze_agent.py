from __future__ import annotations

from typing import Any

from actions.action import LLMAction
from actions.action_node import ActionNode
from agents.base import BaseAgent
from plan.task import TaskType
from schemas.agent_result import AgentResult, fail, ok
from schemas.analysis import AnalysisOutput


_BASE_SYSTEM = "You are a research analysis agent. Analyze information rigorously. Only use facts present in the input — never fabricate."

PROMPT = """\
## Task
{instruction}

## Input Data
{upstream}

Analyze the input data to fulfill the task. Structure your analysis with:
- Key findings (grounded in input data)
- Patterns or relationships observed
- Gaps or limitations in the data
"""


class AnalyzeAgent(BaseAgent):
    skill_file: str = "analyze_skill.md"

    async def run(self, task: dict, upstream: dict[str, Any]) -> AgentResult:
        instruction = task.get("instruction", "")
        task_id = task.get("task_id", "")
        upstream_str = (
            "\n\n".join(f"[{k}]:\n{v}" for k, v in upstream.items())
            if upstream else "(no upstream data)"
        )

        if not upstream:
            return fail(
                self.name, task_id, TaskType.analyze,
                "No upstream data to analyze. Ensure a search or retrieve task runs first.",
            )

        action = self._make_action(LLMAction)
        node = ActionNode(name=self.name, schema_cls=AnalysisOutput)
        node.set_action(action)

        try:
            result = await node.run(
                PROMPT.format(instruction=instruction, upstream=upstream_str),
                system_msg=self._get_system(_BASE_SYSTEM),
            )
            return ok(self.name, task_id, TaskType.analyze, result)
        except Exception as e:
            return fail(self.name, task_id, TaskType.analyze, str(e))

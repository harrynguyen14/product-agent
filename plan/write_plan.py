from __future__ import annotations

# Re-export Plan / Task so existing imports keep working
from plan.model import Plan, Task
from plan.plan_parser import precheck_update_plan_from_rsp, update_plan_from_rsp
from actions.action import ActionContext, LLMAction
from plan.task import TaskType
from utils.response_parser import ResponseParser


PROMPT_TEMPLATE: str = """# Context:
{context}

# Available Task Types:
{task_type_desc}

# Task:
Based on the context, write a plan or modify an existing plan of what you should do to achieve the goal.
A plan consists of one to {max_tasks} tasks.

If you are modifying an existing plan, carefully follow the instruction, don't make unnecessary changes.
Give the whole plan unless instructed to modify only one task of the plan.

If you encounter errors on the current task, revise and output the current single task only.

Output a list of JSON following the format:
```json
[
    {{
        "task_id": "unique identifier for a task in plan, can be an ordinal",
        "dependent_task_ids": ["ids of tasks prerequisite to this task"],
        "instruction": "what you should do in this task, one short phrase or sentence.",
        "task_type": "type of this task, should be one of Available Task Types."
    }}

For tasks of type **search**, the instruction MUST follow this format:
Search: [SPECIFIC TOPIC]
Scope: [time range / source / language if applicable]
Need to know: [specific question to answer]

Good example: "Search: AI agent memory architectures 2024-2025\nScope: academic papers and technical blogs\nNeed to know: types of memory (short-term, long-term, episodic), representative frameworks."
Bad example: "Tìm kiếm về memory cho agent"  ← too vague, will fail.
]
```
"""


class WritePlan(LLMAction):
    """Calls the LLM to generate or update a task plan. Returns raw JSON string."""

    async def run(self, ctx: ActionContext) -> str:
        context = ctx.get("input", [])
        max_tasks: int = ctx.get("config", {}).get("max_tasks", 13)

        task_type_desc = "\n".join(
            f"- **{tt.value}**: {tt.desc}" for tt in TaskType
        )
        context_str = (
            "\n".join(str(c) for c in context)
            if isinstance(context, list)
            else str(context)
        )

        prompt = PROMPT_TEMPLATE.format(
            context=context_str,
            max_tasks=max_tasks,
            task_type_desc=task_type_desc,
        )

        raw = await self.aask(prompt)
        return ResponseParser.parse_json(raw)

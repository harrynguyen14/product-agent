from __future__ import annotations

import json
from copy import deepcopy
from typing import Tuple

from plan.model import Plan, Task


def _parse_tasks(rsp: str) -> list[Task]:
    """Parse a JSON string into a list of Task objects. Raises on invalid input."""
    data = json.loads(rsp)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list, got {type(data).__name__}")
    return [Task(**cfg) for cfg in data]


def update_plan_from_rsp(rsp: str, current_plan: Plan) -> None:
    """Apply a plan response (JSON string) to *current_plan* in place."""
    tasks = _parse_tasks(rsp)

    # Single-task update or partial patch
    if len(tasks) == 1 or (tasks and tasks[0].dependent_task_ids):
        if tasks[0].dependent_task_ids and len(tasks) > 1:
            tasks = tasks[:1]

        task = tasks[0]
        if current_plan.has_task_id(task.task_id):
            current_plan.replace_task(
                task.task_id, task.dependent_task_ids, task.instruction,
                task.task_type, task.assignee,
            )
        else:
            current_plan.append_task(
                task.task_id, task.dependent_task_ids, task.instruction,
                task.task_type, task.assignee,
            )
    else:
        current_plan.add_tasks(tasks)


def precheck_update_plan_from_rsp(rsp: str, current_plan: Plan) -> Tuple[bool, str]:
    """Dry-run update_plan_from_rsp. Returns (is_valid, error_message)."""
    temp_plan = deepcopy(current_plan)
    try:
        update_plan_from_rsp(rsp, temp_plan)
        return True, ""
    except Exception as e:
        return False, str(e)

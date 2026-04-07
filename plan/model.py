from __future__ import annotations

from typing import List, Optional


class Task:
    """Immutable-by-convention data object representing a single plan step."""

    __slots__ = ("task_id", "instruction", "task_type", "dependent_task_ids", "assignee")

    def __init__(
        self,
        task_id: str,
        instruction: str,
        task_type: str = "",
        dependent_task_ids: Optional[List[str]] = None,
        assignee: str = "",
    ) -> None:
        self.task_id = task_id
        self.instruction = instruction
        self.task_type = task_type
        self.dependent_task_ids: List[str] = dependent_task_ids or []
        self.assignee = assignee

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "dependent_task_ids": list(self.dependent_task_ids),
            "instruction": self.instruction,
            "task_type": self.task_type,
        }

    def __repr__(self) -> str:
        return f"Task(id={self.task_id!r}, type={self.task_type!r}, instruction={self.instruction!r})"


class Plan:
    """Ordered collection of Tasks with safe mutation helpers."""

    def __init__(self, tasks: Optional[List[Task]] = None) -> None:
        self._tasks: List[Task] = list(tasks or [])

    # --- read ---

    def has_task_id(self, task_id: str) -> bool:
        return any(t.task_id == task_id for t in self._tasks)

    def to_list(self) -> List[dict]:
        return [t.to_dict() for t in self._tasks]

    def __len__(self) -> int:
        return len(self._tasks)

    def __repr__(self) -> str:
        return f"Plan(tasks={self._tasks!r})"

    # --- write ---

    def add_tasks(self, tasks: List[Task]) -> None:
        self._tasks = list(tasks)

    def append_task(
        self,
        task_id: str,
        dependent_task_ids: List[str],
        instruction: str,
        task_type: str = "",
        assignee: str = "",
    ) -> None:
        self._tasks.append(
            Task(
                task_id=task_id,
                instruction=instruction,
                task_type=task_type,
                dependent_task_ids=dependent_task_ids,
                assignee=assignee,
            )
        )

    def replace_task(
        self,
        task_id: str,
        dependent_task_ids: List[str],
        instruction: str,
        task_type: str = "",
        assignee: str = "",
    ) -> None:
        for i, t in enumerate(self._tasks):
            if t.task_id == task_id:
                self._tasks[i] = Task(
                    task_id=task_id,
                    instruction=instruction,
                    task_type=task_type,
                    dependent_task_ids=dependent_task_ids,
                    assignee=assignee,
                )
                return
        raise ValueError(f"Task {task_id!r} not found in plan")

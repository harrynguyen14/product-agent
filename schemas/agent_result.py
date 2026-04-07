from __future__ import annotations

from typing import Any, Literal, Union

from pydantic import BaseModel


class AgentSuccess(BaseModel):
    kind: Literal["success"] = "success"
    agent: str
    task_id: str
    task_type: str
    output: Any


class AgentFailure(BaseModel):
    kind: Literal["failure"] = "failure"
    agent: str
    task_id: str
    task_type: str
    error: str
    output: Any = None


AgentResult = Union[AgentSuccess, AgentFailure]


def ok(agent: str, task_id: str, task_type: str, output: Any) -> AgentSuccess:
    return AgentSuccess(agent=agent, task_id=task_id, task_type=task_type, output=output)


def fail(agent: str, task_id: str, task_type: str, error: str, output: Any = None) -> AgentFailure:
    return AgentFailure(agent=agent, task_id=task_id, task_type=task_type, error=error, output=output)

from __future__ import annotations

from typing import Any, Callable

from langchain_core.tools import BaseTool

from actions.action import LLMCallable
from agents.analyze_agent import AnalyzeAgent
from agents.base import BaseAgent
from schemas.agent_result import AgentResult
from agents.decompose_agent import DecomposeAgent
from agents.read_agent import ReadAgent
from agents.report_agent import ReportAgent
from agents.retrieve_agent import RetrieveAgent
from agents.search_agent import SearchAgent
from agents.summarize_agent import SummarizeAgent
from agents.synthesize_agent import SynthesizeAgent
from agents.validate_agent import ValidateAgent
from plan.task import TaskType


class AgentRegistry:
    """Maps TaskType values to BaseAgent instances.

    OCP: register() lets callers add new agents without modifying this class.
    DIP: depends on BaseAgent abstraction, not concrete implementations.
    """

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, task_type: str, agent: BaseAgent) -> "AgentRegistry":
        self._agents[task_type] = agent
        return self

    def get(self, task_type: str) -> BaseAgent:
        agent = self._agents.get(task_type)
        if agent is None:
            raise ValueError(f"No agent registered for task_type '{task_type}'")
        return agent

    async def run_task(self, task: dict, upstream: dict[str, Any]) -> AgentResult:
        task_type = task.get("task_type", "")
        agent = self.get(task_type)
        return await agent.run(task, upstream)


def build_default_registry(
    llm: LLMCallable,
    tools: list[BaseTool] | None = None,
    retrieve_fn: Callable[[str, int], list[dict]] | None = None,
    goal: str = "",
) -> AgentRegistry:
    """Factory that wires up the standard set of agents (DIP: wiring lives here, not in runner)."""
    tool_list = tools or []
    search = SearchAgent(tools=tool_list).set_llm(llm)

    registry = AgentRegistry()
    registry.register(TaskType.search,     search)
    registry.register(TaskType.retrieve,   RetrieveAgent(retrieve_fn=retrieve_fn).set_llm(llm))
    registry.register(TaskType.read,       ReadAgent().set_llm(llm))
    registry.register(TaskType.analyze,    AnalyzeAgent().set_llm(llm))
    registry.register(TaskType.synthesize, SynthesizeAgent().set_llm(llm))
    registry.register(TaskType.summarize,  SummarizeAgent().set_llm(llm))
    registry.register(TaskType.report,     ReportAgent(goal=goal).set_llm(llm))
    registry.register(TaskType.validate,   ValidateAgent().set_llm(llm))
    registry.register(TaskType.decompose,  DecomposeAgent().set_llm(llm))
    # mcp / skill / tool reuse SearchAgent — swap via register() if needed
    registry.register(TaskType.mcp,        SearchAgent(tools=tool_list).set_llm(llm))
    registry.register(TaskType.skill,      SearchAgent(tools=tool_list).set_llm(llm))
    registry.register(TaskType.tool,       SearchAgent(tools=tool_list).set_llm(llm))
    return registry

from __future__ import annotations

from typing import Optional

from actions.action import LLMCallable
from langchain_core.tools import BaseTool
from roles.base_role import BaseRole
from roles.product_manager import ProductManager
from roles.planner import RolePlanner
from roles.business_analyst import BusinessAnalyst
from roles.ui_ux_designer import UIUXDesigner
from roles.reporter import Reporter
from roles.security_specialist import SecuritySpecialist
from roles.devops_engineer import DevOpsEngineer
from roles.frontend_dev import FrontendDev
from roles.backend_dev import BackendDev
from roles.software_architect import SoftwareArchitect
from roles.tester import Tester
from roles.project_developer import ProjectDeveloper


# Map: mention string → role class
MENTION_MAP: dict[str, type[BaseRole]] = {
    "/pm":      ProductManager,
    "/planner": RolePlanner,
    "/ba":      BusinessAnalyst,
    "/uiux":    UIUXDesigner,
    "/report":  Reporter,
    "/sec":     SecuritySpecialist,
    "/devops":  DevOpsEngineer,
    "/fe":      FrontendDev,
    "/be":      BackendDev,
    "/arch":    SoftwareArchitect,
    "/qa":      Tester,
    "/pd":      ProjectDeveloper,
}

# Map: role_name → role class
ROLE_NAME_MAP: dict[str, type[BaseRole]] = {
    "ProductManager":     ProductManager,
    "Planner":            RolePlanner,
    "BusinessAnalyst":    BusinessAnalyst,
    "UIUXDesigner":       UIUXDesigner,
    "Reporter":           Reporter,
    "SecuritySpecialist": SecuritySpecialist,
    "DevOpsEngineer":     DevOpsEngineer,
    "FrontendDev":        FrontendDev,
    "BackendDev":         BackendDev,
    "SoftwareArchitect":  SoftwareArchitect,
    "Tester":             Tester,
    "ProjectDeveloper":   ProjectDeveloper,
}


class RoleRegistry:
    """Manages instantiated roles for a session.

    Roles are created lazily and cached.
    When tools are provided, every role gets search access via ReAct loop.
    When a TokenTracker is provided, each role gets its own tracked LLM
    so usage is attributed per role_name.
    """

    def __init__(
        self,
        llm: LLMCallable,
        tools: Optional[list[BaseTool]] = None,
        tracker=None,           # Optional[TokenTracker]
        raw_llm=None,           # raw LangChain model for tracker.wrap()
    ) -> None:
        self._llm = llm
        self._tools: list[BaseTool] = tools or []
        self._tracker = tracker
        self._raw_llm = raw_llm  # needed so tracker.wrap() sees usage_metadata
        self._instances: dict[str, BaseRole] = {}

    def set_tools(self, tools: list[BaseTool]) -> "RoleRegistry":
        """Inject tools into all existing and future role instances."""
        self._tools = list(tools)
        for instance in self._instances.values():
            instance.set_tools(self._tools)
        return self

    def _make_llm(self, role_name: str) -> LLMCallable:
        """Return an LLM for this role — tracked if a tracker is set."""
        if self._tracker is not None and self._raw_llm is not None:
            return self._tracker.wrap(self._raw_llm, role=role_name)
        return self._llm

    def get(self, role_name: str) -> Optional[BaseRole]:
        """Get (or create) a role instance by role_name."""
        if role_name in self._instances:
            return self._instances[role_name]

        cls = ROLE_NAME_MAP.get(role_name)
        if cls is None:
            return None

        instance = cls()
        instance.set_llm(self._make_llm(role_name))
        if self._tools:
            instance.set_tools(self._tools)
        self._instances[role_name] = instance
        return instance

    def get_by_mention(self, mention: str) -> Optional[BaseRole]:
        """Get role by slash-command mention (e.g. '/ba')."""
        cls = MENTION_MAP.get(mention.lower())
        if cls is None:
            return None
        return self.get(cls().role_name)

    def build_team(self, role_names: list[str]) -> dict[str, BaseRole]:
        """Instantiate a set of roles by name. Returns {role_name: instance}."""
        return {name: self.get(name) for name in role_names if self.get(name)}

    def all_mentions(self) -> list[str]:
        return list(MENTION_MAP.keys())

    def all_role_names(self) -> list[str]:
        return list(ROLE_NAME_MAP.keys())

    def clear_histories(self) -> None:
        """Reset conversation history for all instantiated roles."""
        for role in self._instances.values():
            role.clear_history()

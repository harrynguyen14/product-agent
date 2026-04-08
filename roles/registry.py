from __future__ import annotations

from typing import Optional, Any

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
from roles.vietnamese_translator import VietnameseTranslator
from utils.llm_utils import extract_content


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
    "/translate": VietnameseTranslator,
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
    "ProjectDeveloper":      ProjectDeveloper,
    "VietnameseTranslator":  VietnameseTranslator,
}

# Per-role model group routing used when multi_model_enabled=True
#   claude    → Anthropic claude-sonnet-4-6   (code quality, reasoning)
#   gemini25  → Gemini 2.5 Flash              (orchestration, long context)
#   gemini20  → Gemini 2.0 Flash              (fast, lightweight text roles)
ROLE_MODEL_GROUP: dict[str, str] = {
    "SoftwareArchitect":  "claude",
    "BackendDev":         "claude",
    "FrontendDev":        "claude",
    "SecuritySpecialist": "claude",
    "ProductManager":     "gemini25",
    "BusinessAnalyst":    "gemini25",
    "ProjectDeveloper":   "gemini25",
    "Planner":            "gemini25",
    "UIUXDesigner":       "gemini20",
    "DevOpsEngineer":     "gemini20",
    "Tester":             "gemini20",
    "Reporter":              "gemini20",
    "VietnameseTranslator":  "gemini20",
}


class RoleRegistry:
    """Manages instantiated roles for a session.

    Roles are created lazily and cached.
    When tools are provided, every role gets search access via ReAct loop.
    When a TokenTracker is provided, each role gets its own tracked LLM
    so usage is attributed per role_name.
    When a MultiModelSet is provided, each role uses its designated model
    group (claude / gemini25 / gemini20) instead of a single shared LLM.
    """

    def __init__(
        self,
        llm: LLMCallable,
        tools: Optional[list[BaseTool]] = None,
        tracker=None,               # Optional[TokenTracker]
        raw_llm=None,               # raw LangChain model for tracker.wrap()
        multi_model_set=None,       # Optional[MultiModelSet]
        history_window: int = 10,
        react_history_window: int = 6,
    ) -> None:
        self._llm = llm
        self._tools: list[BaseTool] = tools or []
        self._tracker = tracker
        self._raw_llm = raw_llm
        self._multi = multi_model_set
        self._history_window = history_window
        self._react_history_window = react_history_window
        self._instances: dict[str, BaseRole] = {}

    def set_tools(self, tools: list[BaseTool]) -> "RoleRegistry":
        """Inject tools into all existing and future role instances."""
        self._tools = list(tools)
        for instance in self._instances.values():
            instance.set_tools(self._tools)
        return self

    def _make_llm(self, role_name: str) -> LLMCallable:
        """Return an LLM for this role.

        Multi-model mode: routes to claude / gemini25 / gemini20 based on ROLE_MODEL_GROUP.
        Single-model mode: uses shared _raw_llm (tracked) or plain _llm.
        """
        if self._multi is not None:
            group = ROLE_MODEL_GROUP.get(role_name, "gemini25")
            raw = {
                "claude":   self._multi.raw_claude,
                "gemini25": self._multi.raw_gemini25,
                "gemini20": self._multi.raw_gemini20,
            }[group]
            if self._tracker is not None:
                return self._tracker.wrap(raw, role=role_name)
            # Plain async wrapper when no tracker
            async def _call_multi(messages, _raw=raw) -> str:
                response = await _raw.ainvoke(messages)
                return extract_content(response)
            return _call_multi

        # Single-model path (unchanged behavior)
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
        instance.history_window = self._history_window
        instance.react_history_window = self._react_history_window
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

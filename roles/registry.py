from __future__ import annotations

from typing import Optional

from core.llm_factory import LLMCallable, LLMFactory, MultiModelSet
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


# Map: role_name → role class
ROLE_NAME_MAP: dict[str, type[BaseRole]] = {
    "ProductManager":       ProductManager,
    "Planner":              RolePlanner,
    "BusinessAnalyst":      BusinessAnalyst,
    "UIUXDesigner":         UIUXDesigner,
    "Reporter":             Reporter,
    "SecuritySpecialist":   SecuritySpecialist,
    "DevOpsEngineer":       DevOpsEngineer,
    "FrontendDev":          FrontendDev,
    "BackendDev":           BackendDev,
    "SoftwareArchitect":    SoftwareArchitect,
    "Tester":               Tester,
    "ProjectDeveloper":     ProjectDeveloper,
    "VietnameseTranslator": VietnameseTranslator,
}

# Per-role model group khi dùng multi_model_enabled
ROLE_MODEL_GROUP: dict[str, str] = {
    "SoftwareArchitect":    "claude",
    "BackendDev":           "claude",
    "FrontendDev":          "claude",
    "SecuritySpecialist":   "claude",
    "ProductManager":       "gemini25",
    "BusinessAnalyst":      "gemini25",
    "ProjectDeveloper":     "gemini25",
    "Planner":              "gemini25",
    "UIUXDesigner":         "gemini20",
    "DevOpsEngineer":       "gemini20",
    "Tester":               "gemini20",
    "Reporter":             "gemini20",
    "VietnameseTranslator": "gemini20",
}


class RoleRegistry:
    """Quản lý và cache các role instance cho 1 bot session."""

    def __init__(
        self,
        llm: LLMCallable,
        raw_llm=None,
        multi_model_set: Optional[MultiModelSet] = None,
        history_window: int = 10,
    ) -> None:
        self._llm = llm
        self._raw_llm = raw_llm
        self._multi = multi_model_set
        self._history_window = history_window
        self._instances: dict[str, BaseRole] = {}

    def _make_llm(self, role_name: str) -> LLMCallable:
        if self._multi is not None:
            group = ROLE_MODEL_GROUP.get(role_name, "gemini25")
            raw = {
                "claude":   self._multi.raw_claude,
                "gemini25": self._multi.raw_gemini25,
                "gemini20": self._multi.raw_gemini20,
            }[group]

            async def _call_multi(messages, _raw=raw) -> str:
                response = await _raw.ainvoke(messages)
                return extract_content(response)

            return _call_multi

        return self._llm

    def get(self, role_name: str) -> Optional[BaseRole]:
        """Lấy (hoặc tạo mới) role instance theo role_name."""
        if role_name in self._instances:
            return self._instances[role_name]

        cls = ROLE_NAME_MAP.get(role_name)
        if cls is None:
            return None

        instance = cls()
        instance.history_window = self._history_window
        instance.set_llm(self._make_llm(role_name))
        self._instances[role_name] = instance
        return instance

    def all_role_names(self) -> list[str]:
        return list(ROLE_NAME_MAP.keys())

    def clear_histories(self) -> None:
        for role in self._instances.values():
            role.clear_history()

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from langchain_core.tools import BaseTool


@dataclass
class ToolInfo:
    name: str
    description: str
    category: str
    tool: BaseTool


# ---------------------------------------------------------------------------
# Abstract interface — callers depend on this, not the concrete class (DIP)
# ---------------------------------------------------------------------------

class AbstractToolRegistry(ABC):
    @abstractmethod
    def register_tool(self, tool: BaseTool) -> None: ...

    @abstractmethod
    def register_skill(self, tool: BaseTool) -> None: ...

    @abstractmethod
    def register_mcp(self, tool: BaseTool) -> None: ...

    @abstractmethod
    def get(self, name: str) -> BaseTool | None: ...

    @abstractmethod
    def all_tools(self) -> list[BaseTool]: ...

    @abstractmethod
    def stats(self) -> dict[str, Any]: ...

    @abstractmethod
    def all_infos(self) -> list[ToolInfo]: ...


# ---------------------------------------------------------------------------
# Concrete implementation
# ---------------------------------------------------------------------------

class ToolRegistry(AbstractToolRegistry):
    def __init__(self) -> None:
        self._tools: dict[str, ToolInfo] = {}
        self._skills: dict[str, ToolInfo] = {}
        self._mcp: dict[str, ToolInfo] = {}

    def register_tool(self, tool: BaseTool) -> None:
        self._tools[tool.name] = ToolInfo(
            name=tool.name, description=tool.description or "", category="tool", tool=tool
        )

    def register_skill(self, tool: BaseTool) -> None:
        self._skills[tool.name] = ToolInfo(
            name=tool.name, description=tool.description or "", category="skill", tool=tool
        )

    def register_mcp(self, tool: BaseTool) -> None:
        self._mcp[tool.name] = ToolInfo(
            name=tool.name, description=tool.description or "", category="mcp", tool=tool
        )

    def get(self, name: str) -> BaseTool | None:
        for store in (self._tools, self._skills, self._mcp):
            if name in store:
                return store[name].tool
        return None

    def all_tools(self) -> list[BaseTool]:
        seen: dict[str, BaseTool] = {}
        for store in (self._tools, self._skills, self._mcp):
            for name, info in store.items():
                seen.setdefault(name, info.tool)
        return list(seen.values())

    def stats(self) -> dict[str, Any]:
        return {
            "tools":  {"count": len(self._tools),  "names": list(self._tools)},
            "skills": {"count": len(self._skills), "names": list(self._skills)},
            "mcp":    {"count": len(self._mcp),    "names": list(self._mcp)},
            "total":  len(self._tools) + len(self._skills) + len(self._mcp),
        }

    def all_infos(self) -> list[ToolInfo]:
        result: list[ToolInfo] = []
        for store in (self._tools, self._skills, self._mcp):
            result.extend(store.values())
        return result


# ---------------------------------------------------------------------------
# Factory helper — creates a pre-loaded registry (replaces global singleton)
# ---------------------------------------------------------------------------

def build_default_registry() -> ToolRegistry:
    """Create and return a ToolRegistry loaded with default tools."""
    from tools.web_search import web_search_tool
    registry = ToolRegistry()
    registry.register_tool(web_search_tool)
    return registry

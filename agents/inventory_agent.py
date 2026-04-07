from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from tools.registry import ToolInfo, ToolRegistry


@dataclass
class InventoryReport:
    stats: dict[str, Any]
    relevant_tools: list[str]
    relevant_skills: list[str]
    relevant_mcp: list[str]

    def has_any(self) -> bool:
        return bool(self.relevant_tools or self.relevant_skills or self.relevant_mcp)

    def context_str(self) -> str:
        lines = [
            f"## Available Components",
            f"- Tools:  {self.stats['tools']['count']} ({', '.join(self.stats['tools']['names']) or 'none'})",
            f"- Skills: {self.stats['skills']['count']} ({', '.join(self.stats['skills']['names']) or 'none'})",
            f"- MCP:    {self.stats['mcp']['count']} ({', '.join(self.stats['mcp']['names']) or 'none'})",
            f"- Total:  {self.stats['total']}",
            "",
            "## Relevant to Current Goal",
        ]
        if self.relevant_tools:
            lines.append(f"- Tools:  {', '.join(self.relevant_tools)}")
        if self.relevant_skills:
            lines.append(f"- Skills: {', '.join(self.relevant_skills)}")
        if self.relevant_mcp:
            lines.append(f"- MCP:    {', '.join(self.relevant_mcp)}")
        if not self.has_any():
            lines.append("  (none matched)")
        return "\n".join(lines)


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9]+", text.lower()))


def _bm25_score(query_tokens: set[str], doc: str) -> int:
    doc_tokens = _tokenize(doc)
    return len(query_tokens & doc_tokens)


def _find_relevant(goal: str, infos: list[ToolInfo], threshold: int = 1) -> dict[str, list[str]]:
    query_tokens = _tokenize(goal)
    result: dict[str, list[str]] = {"tool": [], "skill": [], "mcp": []}

    for info in infos:
        score = _bm25_score(query_tokens, f"{info.name} {info.description}")
        if score >= threshold:
            result[info.category].append(info.name)

    return result


class InventoryAgent:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def check(self, goal: str) -> InventoryReport:
        stats = self.registry.stats()
        infos = self.registry.all_infos()
        relevant = _find_relevant(goal, infos)

        return InventoryReport(
            stats=stats,
            relevant_tools=relevant["tool"],
            relevant_skills=relevant["skill"],
            relevant_mcp=relevant["mcp"],
        )

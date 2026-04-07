from __future__ import annotations

from typing import Any, Union

from pydantic import BaseModel, field_validator


def _to_str_list(v: Any) -> list[str]:
    """Coerce any value to list[str] — handles str, list[dict], list[str] from LLMs."""
    if isinstance(v, str):
        items = [line.strip(" -•*") for line in v.splitlines() if line.strip()]
        return items if len(items) > 1 else [v]
    if not isinstance(v, list):
        return [str(v)]
    result = []
    for item in v:
        if isinstance(item, dict):
            result.append(next(iter(item.values()), str(item)))
        else:
            result.append(str(item))
    return result


def _to_str(v: Any) -> str:
    """Coerce list[str] to newline-joined string."""
    if isinstance(v, list):
        return "\n".join(str(item) for item in v)
    return v


def _to_dict_list(v: Any) -> list[dict]:
    """Coerce to list[dict] — handles list[str] by wrapping each item."""
    if not isinstance(v, list):
        return []
    result = []
    for item in v:
        if isinstance(item, dict):
            result.append(item)
        elif isinstance(item, str):
            result.append({"finding": item, "detail": "", "source": ""})
    return result


class ReportOutput(BaseModel):
    # ── Core content ──────────────────────────────────────────────────────────
    title: str = ""
    executive_summary: str = ""
    main_conclusion: str = ""
    final_recommendation: str = ""

    # ── Findings — two representations ───────────────────────────────────────
    # findings: flat list (legacy, kept for backward compat)
    # findings_table: structured rows with source citations
    key_findings: list[str] = []
    key_facts: list[str] = []
    findings: list[str] = []
    findings_table: list[dict] = []   # [{"finding": "...", "detail": "...", "source": "..."}]

    # ── Analysis ─────────────────────────────────────────────────────────────
    analysis: str = ""

    # ── Gaps, risks, recs ────────────────────────────────────────────────────
    knowledge_gaps: list[str] = []
    risks: list[str] = []
    recommendations: str = ""

    # ── Provenance & methodology ─────────────────────────────────────────────
    sources: list[str] = []        # ["[1] Title — URL", "[2] ..."]
    methodology: str = ""          # how data was collected (search queries, tools used)

    # ── Delivery ─────────────────────────────────────────────────────────────
    telegram_summary: str = ""     # 2-3 sentence summary for Telegram message
    confidence_score: float = 0.0  # 0.0–1.0, computed from upstream completeness

    # ── Validators ───────────────────────────────────────────────────────────
    @field_validator(
        "key_findings", "key_facts", "findings",
        "knowledge_gaps", "risks", "sources",
        mode="before",
    )
    @classmethod
    def _coerce_str_list(cls, v):
        return _to_str_list(v)

    @field_validator(
        "recommendations", "analysis", "executive_summary",
        "main_conclusion", "final_recommendation",
        "telegram_summary", "methodology",
        mode="before",
    )
    @classmethod
    def _coerce_str(cls, v):
        return _to_str(v)

    @field_validator("findings_table", mode="before")
    @classmethod
    def _coerce_dict_list(cls, v):
        return _to_dict_list(v)

    def __str__(self) -> str:
        return self.executive_summary or self.main_conclusion or self.title

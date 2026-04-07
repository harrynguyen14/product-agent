from __future__ import annotations

from pydantic import BaseModel


class AnalysisOutput(BaseModel):
    key_findings: list[str] = []
    patterns: list[str] = []
    gaps: list[str] = []
    summary: str = ""

    def __str__(self) -> str:
        return self.summary

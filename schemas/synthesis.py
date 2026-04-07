from __future__ import annotations

from pydantic import BaseModel


class SynthesisOutput(BaseModel):
    unified_result: str = ""
    consensus_points: list[str] = []
    contradictions: list[str] = []
    uncertainties: list[str] = []

    def __str__(self) -> str:
        return self.unified_result

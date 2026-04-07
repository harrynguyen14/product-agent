from __future__ import annotations

from pydantic import BaseModel, Field


class WebSearchInput(BaseModel):
    query: str = Field(description="Search query string")
    num_results: int = Field(default=5, description="Number of results to return")

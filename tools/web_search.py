from __future__ import annotations

import os
from typing import Any

import httpx
from langchain_core.tools import BaseTool, StructuredTool

from schemas.tool_inputs import WebSearchInput

__all__ = ["WebSearchInput", "web_search_tool"]


async def _web_search(query: str, num_results: int = 5) -> list[dict[str, str]]:
    api_key = os.getenv("SERPAPI_API_KEY", "")
    if not api_key:
        raise RuntimeError("SERPAPI_API_KEY not set in environment")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            "https://serpapi.com/search",
            params={
                "q": query,
                "num": num_results,
                "api_key": api_key,
                "engine": "google",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("organic_results", [])[:num_results]:
        results.append({
            "title": item.get("title", ""),
            "url": item.get("link", ""),
            "snippet": item.get("snippet", ""),
        })
    return results


async def web_search(query: str, num_results: int = 5) -> str:
    results = await _web_search(query, num_results)
    if not results:
        return "No results found."
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r['title']}\n    URL: {r['url']}\n    {r['snippet']}")
    return "\n\n".join(lines)


web_search_tool: BaseTool = StructuredTool.from_function(
    coroutine=web_search,
    name="web_search",
    description="Search the web via Google (SerpAPI). Returns titles, URLs, and snippets.",
    args_schema=WebSearchInput,
)

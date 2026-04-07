from __future__ import annotations

"""TokenTracker — per-role token usage tracking for a single task session.

Usage
-----
    tracker = TokenTracker()

    # Wrap an LLMCallable so every call is automatically recorded
    tracked_llm = tracker.wrap(llm, role="BusinessAnalyst")

    # At any point, inspect usage
    tracker.summary()          # dict: totals + per-role breakdown
    tracker.format_report()    # human-readable string for Discord
    tracker.reset()            # clear for next task
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional

from infrastructure.logging import get_logger

logger = get_logger("token_tracker")


@dataclass
class RoleUsage:
    role: str
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class TokenTracker:
    """Tracks LLM token usage per role across a task session.

    Thread-safe via asyncio.Lock — safe for concurrent role execution (parallel phases).
    """

    def __init__(self) -> None:
        self._usage: dict[str, RoleUsage] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Core recording
    # ------------------------------------------------------------------

    async def record(self, role: str, input_tokens: int, output_tokens: int) -> None:
        async with self._lock:
            if role not in self._usage:
                self._usage[role] = RoleUsage(role=role)
            u = self._usage[role]
            u.input_tokens += input_tokens
            u.output_tokens += output_tokens
            u.calls += 1

        logger.debug(
            "token_record",
            role=role,
            input=input_tokens,
            output=output_tokens,
            calls=self._usage[role].calls,
        )

    # ------------------------------------------------------------------
    # Wrap an LLMCallable
    # ------------------------------------------------------------------

    def wrap(self, llm, role: str):
        """Return a new LLMCallable that records token usage automatically.

        Works with any LangChain response that exposes usage_metadata
        (Anthropic, OpenAI, Gemini all do). Falls back to 0 tokens if
        the provider doesn't expose usage (Ollama, LM Studio local models).
        """
        tracker = self

        async def tracked_llm(messages) -> str:
            # raw_llm is a LangChain chat model — use ainvoke, not __call__
            response = await llm.ainvoke(messages)

            # Extract token counts from usage_metadata (Anthropic / OpenAI / Gemini)
            input_tokens = 0
            output_tokens = 0

            if hasattr(response, "usage_metadata") and response.usage_metadata:
                meta = response.usage_metadata
                if isinstance(meta, dict):
                    input_tokens = meta.get("input_tokens", 0)
                    output_tokens = meta.get("output_tokens", 0)
                else:
                    input_tokens = getattr(meta, "input_tokens", 0)
                    output_tokens = getattr(meta, "output_tokens", 0)
            elif hasattr(response, "response_metadata"):
                # OpenAI-style fallback: response_metadata.token_usage
                meta = response.response_metadata or {}
                usage = meta.get("token_usage") or meta.get("usage", {})
                if isinstance(usage, dict):
                    input_tokens = usage.get("prompt_tokens", 0)
                    output_tokens = usage.get("completion_tokens", 0)

            await tracker.record(role, input_tokens, output_tokens)

            # Return plain string content
            content = response.content if hasattr(response, "content") else str(response)
            if isinstance(content, list):
                content = "\n".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            return content

        return tracked_llm

    # ------------------------------------------------------------------
    # Summary / reporting
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        """Return structured usage summary."""
        rows = sorted(self._usage.values(), key=lambda u: u.total_tokens, reverse=True)
        total_input = sum(u.input_tokens for u in rows)
        total_output = sum(u.output_tokens for u in rows)
        return {
            "total": {
                "input_tokens": total_input,
                "output_tokens": total_output,
                "total_tokens": total_input + total_output,
                "calls": sum(u.calls for u in rows),
            },
            "by_role": [
                {
                    "role": u.role,
                    "input_tokens": u.input_tokens,
                    "output_tokens": u.output_tokens,
                    "total_tokens": u.total_tokens,
                    "calls": u.calls,
                }
                for u in rows
            ],
        }

    def format_report(self, model: str = "") -> str:
        """Human-readable token report for Discord."""
        s = self.summary()
        t = s["total"]

        if t["total_tokens"] == 0:
            return "📊 **Token Usage** — không có dữ liệu (provider không hỗ trợ usage tracking)"

        lines = ["📊 **Token Usage Summary**"]
        if model:
            lines.append(f"*Model: {model}*")
        lines.append("")

        # Per-role table
        lines.append("```")
        lines.append(f"{'Role':<22} {'Input':>8} {'Output':>8} {'Total':>8} {'Calls':>6}")
        lines.append("─" * 56)
        for row in s["by_role"]:
            lines.append(
                f"{row['role']:<22} {row['input_tokens']:>8,} {row['output_tokens']:>8,} "
                f"{row['total_tokens']:>8,} {row['calls']:>6}"
            )
        lines.append("─" * 56)
        lines.append(
            f"{'TOTAL':<22} {t['input_tokens']:>8,} {t['output_tokens']:>8,} "
            f"{t['total_tokens']:>8,} {t['calls']:>6}"
        )
        lines.append("```")

        return "\n".join(lines)

    def reset(self) -> None:
        """Clear all recorded usage (call before each new task)."""
        self._usage.clear()
        logger.debug("token_tracker_reset")

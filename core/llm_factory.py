from __future__ import annotations

from typing import Optional

from actions.action import LLMCallable
from config.provider_config import ProviderConfig
from providers.providers import Provider


def _extract_content(response) -> str:
    """Extract text content from a LangChain response object."""
    content = response.content if hasattr(response, "content") else str(response)
    if isinstance(content, list):
        content = "\n".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return content


class LLMFactory:
    """Single responsibility: build an LLMCallable from a ProviderConfig."""

    @staticmethod
    def build(config: ProviderConfig, tracker=None, role: str = "unknown") -> LLMCallable:
        """Build an LLMCallable.

        Args:
            config:  Provider configuration.
            tracker: Optional TokenTracker. When provided, token usage is
                     recorded for every call under the given role name.
            role:    Role name to attribute usage to (used with tracker).
        """
        provider = Provider(**config.model_dump())
        llm = provider.get_provider()

        if tracker is not None:
            # Return a tracked callable — tracker reads usage_metadata directly
            return tracker.wrap(llm, role=role)

        # Plain callable (no tracking)
        async def call_llm(messages) -> str:
            response = await llm.ainvoke(messages)
            return _extract_content(response)

        return call_llm

    @staticmethod
    def build_raw(config: ProviderConfig):
        """Return the raw LangChain chat model (for use with TokenTracker.wrap)."""
        provider = Provider(**config.model_dump())
        return provider.get_provider()

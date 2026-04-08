from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from actions.action import LLMCallable
from config.provider_config import LLMProvider, ProviderConfig
from providers.providers import Provider
from utils.llm_utils import extract_content


@dataclass
class MultiModelSet:
    """Three pre-built raw LangChain models for per-role routing.

    Group A (claude)    — SoftwareArchitect, BackendDev, FrontendDev, SecuritySpecialist
    Group B (gemini25)  — ProductManager, BusinessAnalyst, ProjectDeveloper, Planner
    Group C (gemini20)  — UIUXDesigner, DevOpsEngineer, Tester, Reporter
    """
    raw_claude: Any
    raw_gemini25: Any
    raw_gemini20: Any


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
            return tracker.wrap(llm, role=role)

        async def call_llm(messages) -> str:
            response = await llm.ainvoke(messages)
            return extract_content(response)

        return call_llm

    @staticmethod
    def build_raw(config: ProviderConfig):
        """Return the raw LangChain chat model (for use with TokenTracker.wrap)."""
        provider = Provider(**config.model_dump())
        return provider.get_provider()

    @staticmethod
    def _build_raw_override(config: ProviderConfig, provider_enum: LLMProvider, model: str):
        """Build a raw LangChain model for a specific provider+model, ignoring config.llm_provider."""
        overrides: dict[str, Any] = {"llm_provider": provider_enum}
        # Map provider enum to config field name
        field_map = {
            LLMProvider.ANTHROPIC: "anthropic_provider",
            LLMProvider.GEMINI:    "gemini_provider",
            LLMProvider.OPENAI:    "openai_provider",
            LLMProvider.OLLAMA:    "ollama_provider",
            LLMProvider.LMSTUDIO:  "lmstudio_provider",
        }
        if provider_enum in field_map:
            overrides[field_map[provider_enum]] = model
        overridden = config.model_copy(update=overrides)
        return LLMFactory.build_raw(overridden)

    @staticmethod
    def build_multi(config: ProviderConfig) -> MultiModelSet:
        """Build all three model groups for per-role routing.

        Requires:
            - MA_ANTHROPIC_API_KEY set (for Group A — Claude)
            - MA_GEMINI_API_KEY set (for Group B + C — Gemini)

        Raises:
            ValueError if required API keys are missing.
        """
        if not config.anthropic_api_key:
            raise ValueError(
                "multi_model_enabled=True requires MA_ANTHROPIC_API_KEY to be set "
                "(used for SoftwareArchitect, BackendDev, FrontendDev, SecuritySpecialist)."
            )
        if not config.gemini_api_key:
            raise ValueError(
                "multi_model_enabled=True requires MA_GEMINI_API_KEY to be set "
                "(used for ProductManager, BusinessAnalyst, ProjectDeveloper, Planner, "
                "UIUXDesigner, DevOpsEngineer, Tester, Reporter)."
            )

        raw_claude = LLMFactory._build_raw_override(
            config, LLMProvider.ANTHROPIC, config.anthropic_multi_provider
        )
        raw_gemini25 = LLMFactory._build_raw_override(
            config, LLMProvider.GEMINI, config.gemini_reasoning_provider
        )
        raw_gemini20 = LLMFactory._build_raw_override(
            config, LLMProvider.GEMINI, config.gemini_fast_provider
        )

        return MultiModelSet(
            raw_claude=raw_claude,
            raw_gemini25=raw_gemini25,
            raw_gemini20=raw_gemini20,
        )

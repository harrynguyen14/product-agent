from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from typing import Callable, Awaitable
from config.provider_config import LLMProvider, ProviderConfig

# Type alias cho LLM callable
LLMCallable = Callable[..., Awaitable[str]]
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
    def _build_fallback_raw(config: ProviderConfig):
        """Build a raw LangChain model from the fallback provider config.

        Reads MA_FALLBACK_PROVIDER, MA_FALLBACK_API_KEY, MA_FALLBACK_MODEL.
        Returns None if fallback is not configured.
        """
        if not config.fallback_provider:
            return None

        try:
            provider_enum = LLMProvider(config.fallback_provider.lower())
        except ValueError:
            return None

        # Determine model: use fallback_model if set, otherwise the provider's default
        field_map = {
            LLMProvider.ANTHROPIC: ("anthropic_provider", "anthropic_api_key"),
            LLMProvider.GEMINI:    ("gemini_provider",    "gemini_api_key"),
            LLMProvider.OPENAI:    ("openai_provider",    "openai_api_key"),
            LLMProvider.OLLAMA:    ("ollama_provider",    None),
            LLMProvider.LMSTUDIO:  ("lmstudio_provider",  None),
        }
        model_field, key_field = field_map.get(provider_enum, (None, None))
        if model_field is None:
            return None

        overrides: dict[str, Any] = {"llm_provider": provider_enum}
        if config.fallback_model:
            overrides[model_field] = config.fallback_model
        if key_field and config.fallback_api_key:
            overrides[key_field] = config.fallback_api_key

        overridden = config.model_copy(update=overrides)
        return LLMFactory.build_raw(overridden)

    @staticmethod
    def build_multi(config: ProviderConfig) -> MultiModelSet:
        """Build all three model groups for per-role routing.

        When MA_ANTHROPIC_API_KEY or MA_GEMINI_API_KEY is missing, the affected
        group(s) fall back to the fallback provider defined by:
            MA_FALLBACK_PROVIDER  — provider name (e.g. "openai", "gemini", "anthropic")
            MA_FALLBACK_API_KEY   — API key for that provider
            MA_FALLBACK_MODEL     — model name (optional)

        Raises:
            ValueError if a required API key is missing AND no fallback is configured.
        """
        fallback_raw = LLMFactory._build_fallback_raw(config)

        has_anthropic = bool(config.anthropic_api_key)
        has_gemini = bool(config.gemini_api_key)

        if not has_anthropic and fallback_raw is None:
            raise ValueError(
                "multi_model_enabled=True requires MA_ANTHROPIC_API_KEY to be set "
                "(used for SoftwareArchitect, BackendDev, FrontendDev, SecuritySpecialist). "
                "Alternatively, set MA_FALLBACK_PROVIDER + MA_FALLBACK_API_KEY to use a fallback."
            )
        if not has_gemini and fallback_raw is None:
            raise ValueError(
                "multi_model_enabled=True requires MA_GEMINI_API_KEY to be set "
                "(used for ProductManager, BusinessAnalyst, ProjectDeveloper, Planner, "
                "UIUXDesigner, DevOpsEngineer, Tester, Reporter). "
                "Alternatively, set MA_FALLBACK_PROVIDER + MA_FALLBACK_API_KEY to use a fallback."
            )

        raw_claude = (
            LLMFactory._build_raw_override(config, LLMProvider.ANTHROPIC, config.anthropic_multi_provider)
            if has_anthropic else fallback_raw
        )
        raw_gemini25 = (
            LLMFactory._build_raw_override(config, LLMProvider.GEMINI, config.gemini_reasoning_provider)
            if has_gemini else fallback_raw
        )
        raw_gemini20 = (
            LLMFactory._build_raw_override(config, LLMProvider.GEMINI, config.gemini_fast_provider)
            if has_gemini else fallback_raw
        )

        return MultiModelSet(
            raw_claude=raw_claude,
            raw_gemini25=raw_gemini25,
            raw_gemini20=raw_gemini20,
        )

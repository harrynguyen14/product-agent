from config.provider_config import LLMProvider, ProviderConfig

# API keys required per cloud provider (local providers like Ollama/LMStudio don't need one)
_PROVIDER_KEY: dict[LLMProvider, str] = {
    LLMProvider.ANTHROPIC: "anthropic_api_key",
    LLMProvider.OPENAI:    "openai_api_key",
    LLMProvider.GEMINI:    "gemini_api_key",
}


class Provider(ProviderConfig):
    def get_active_provider(self) -> str:
        return {
            LLMProvider.ANTHROPIC: self.anthropic_provider,
            LLMProvider.OPENAI: self.openai_provider,
            LLMProvider.GEMINI: self.gemini_provider,
            LLMProvider.OLLAMA: self.ollama_provider,
            LLMProvider.LMSTUDIO: self.lmstudio_provider,
        }[self.llm_provider]

    def _resolve_provider(self) -> LLMProvider:
        """Return the effective provider, falling back when the primary API key is missing."""
        primary = self.llm_provider
        key_field = _PROVIDER_KEY.get(primary)
        if key_field is not None and not getattr(self, key_field, ""):
            # Primary key missing — try to fall back
            if self.fallback_provider:
                try:
                    return LLMProvider(self.fallback_provider.lower())
                except ValueError:
                    pass
        return primary

    def get_provider(self):
        provider = self._resolve_provider()

        # is_fallback = primary key was missing AND we have fallback config
        primary_key_field = _PROVIDER_KEY.get(self.llm_provider)
        primary_key_missing = bool(
            primary_key_field and not getattr(self, primary_key_field, "")
        )
        is_fallback = primary_key_missing and bool(self.fallback_provider)

        # When using fallback, prefer fallback_api_key / fallback_model when set
        def _api_key(default: str) -> str:
            return self.fallback_api_key if is_fallback and self.fallback_api_key else default

        def _model(default: str) -> str:
            return self.fallback_model if is_fallback and self.fallback_model else default

        if provider == LLMProvider.ANTHROPIC:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=_model(self.anthropic_provider),
                api_key=_api_key(self.anthropic_api_key),
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

        elif provider == LLMProvider.OPENAI:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=_model(self.openai_provider),
                api_key=_api_key(self.openai_api_key),
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

        elif provider == LLMProvider.GEMINI:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=_model(self.gemini_provider),
                google_api_key=_api_key(self.gemini_api_key),
                temperature=self.temperature,
                max_output_tokens=self.max_tokens,
            )

        elif provider == LLMProvider.OLLAMA:
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=_model(self.ollama_provider),
                base_url=self.ollama_base_url,
                temperature=self.temperature,
                num_predict=self.max_tokens,
                num_ctx=self.ollama_num_ctx,
            )

        elif provider == LLMProvider.LMSTUDIO:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=_model(self.lmstudio_provider),
                api_key=_api_key(self.lmstudio_api_key),
                base_url=self.lmstudio_base_url,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

        raise ValueError(f"Unsupported provider: {provider}")
from config.provider_config import LLMProvider, ProviderConfig

class Provider(ProviderConfig):
    def get_active_provider(self) -> str:
        return {
            LLMProvider.ANTHROPIC: self.anthropic_provider,
            LLMProvider.OPENAI: self.openai_provider,
            LLMProvider.GEMINI: self.gemini_provider,
            LLMProvider.OLLAMA: self.ollama_provider,
            LLMProvider.LMSTUDIO: self.lmstudio_provider,
        }[self.llm_provider]

    def get_provider(self):
        provider = self.llm_provider

        if provider == LLMProvider.ANTHROPIC:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=self.anthropic_provider,
                api_key=self.anthropic_api_key,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

        elif provider == LLMProvider.OPENAI:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=self.openai_provider,
                api_key=self.openai_api_key,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

        elif provider == LLMProvider.GEMINI:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=self.gemini_provider,
                google_api_key=self.gemini_api_key,
                temperature=self.temperature,
                max_output_tokens=self.max_tokens,
            )

        elif provider == LLMProvider.OLLAMA:
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=self.ollama_provider,
                base_url=self.ollama_base_url,
                temperature=self.temperature,
                num_predict=self.max_tokens,
                num_ctx=self.ollama_num_ctx,
            )

        elif provider == LLMProvider.LMSTUDIO:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=self.lmstudio_provider,
                api_key=self.lmstudio_api_key,
                base_url=self.lmstudio_base_url,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

        raise ValueError(f"Unsupported provider: {provider}")
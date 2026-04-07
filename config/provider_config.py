from enum import Enum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OLLAMA = "ollama"
    LMSTUDIO = "lmstudio"


class ProviderConfig(BaseSettings):
    llm_provider: LLMProvider = Field(default=LLMProvider.GEMINI)

    # --- Anthropic ---
    anthropic_api_key: str = ""
    anthropic_provider: str = "claude-opus-4-6"

    # --- OpenAI ---
    openai_api_key: str = ""
    openai_provider: str = "gpt-4o"

    # --- Gemini ---
    gemini_api_key: str = ""
    gemini_provider: str = "gemini-2.0-flash"

    # --- Ollama ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_provider: str = "llama3.2"
    ollama_num_ctx: int = 4096

    # --- LM Studio ---
    lmstudio_base_url: str = "http://localhost:1234/v1"
    lmstudio_provider: str = "local-model"
    lmstudio_api_key: str = "lm-studio"

    # --- Params ---
    max_tokens: int = 4096
    temperature: float = 0.0
    top_p: float = 1.0
    timeout: int = 300

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MA_",
        case_sensitive=False,
        extra="ignore",
    )


def get_config() -> ProviderConfig:
    return ProviderConfig()
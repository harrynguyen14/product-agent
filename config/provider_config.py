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

    # --- Multi-model routing (off by default) ---
    # When True, each role uses its designated model group instead of a single LLM.
    # Requires MA_ANTHROPIC_API_KEY + MA_GEMINI_API_KEY to both be set.
    multi_model_enabled: bool = Field(default=False)
    # Anthropic model used for code-heavy roles (Arch, BE, FE, Security)
    anthropic_multi_provider: str = Field(default="claude-sonnet-4-6")
    # Fast Gemini model used for lightweight roles (UIUX, DevOps, Tester, Reporter)
    gemini_fast_provider: str = Field(default="gemini-2.0-flash")
    # Reasoning Gemini model used for orchestrator roles (PM, BA, PD, Planner)
    gemini_reasoning_provider: str = Field(default="gemini-2.5-flash-preview-04-17")

    # --- Token optimization ---
    # When True, PM summarizes each phase output before passing to next phase
    compress_phases: bool = Field(default=False)
    # Max conversation turns kept in role history (sliding window)
    role_history_window: int = Field(default=10)
    role_react_history_window: int = Field(default=6)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MA_",
        case_sensitive=False,
        extra="ignore",
    )


def get_config() -> ProviderConfig:
    return ProviderConfig()
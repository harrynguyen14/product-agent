from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.provider_config import LLMProvider, ProviderConfig


class AppConfig(ProviderConfig):
    needs_writing: bool = Field(default=True)
    max_retries: int = Field(default=3)
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="console")
    streaming_enabled: bool = Field(default=True)
    telegram_bot_token: str = Field(default="")
    # Discord
    discord_bot_token: str = Field(default="")
    discord_guild_id: int = Field(default=0)
    discord_main_channel_id: int = Field(default=0)
    mcp_enabled: bool = Field(default=False)
    mcp_config_file: str = Field(default="")
    skills_enabled: bool = Field(default=False)
    skill_names: list[str] = Field(default_factory=list)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MA_",
        case_sensitive=False,
        extra="ignore",
    )

    def get_active_model(self) -> str:
        return {
            LLMProvider.ANTHROPIC: self.anthropic_provider,
            LLMProvider.OPENAI:    self.openai_provider,
            LLMProvider.GEMINI:    self.gemini_provider,
            LLMProvider.OLLAMA:    self.ollama_provider,
            LLMProvider.LMSTUDIO:  self.lmstudio_provider,
        }[self.llm_provider]


def get_config() -> AppConfig:
    return AppConfig()

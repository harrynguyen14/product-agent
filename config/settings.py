from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.provider_config import LLMProvider, ProviderConfig

# Tất cả role names hợp lệ
ALL_ROLES = [
    "pm", "planner", "ba", "uiux", "pd",
    "arch", "sec", "devops", "fe", "be", "qa", "reporter",
]

# Map role slug → RoleRegistry role_name
ROLE_SLUG_TO_NAME: dict[str, str] = {
    "pm":       "ProductManager",
    "planner":  "Planner",
    "ba":       "BusinessAnalyst",
    "uiux":     "UIUXDesigner",
    "pd":       "ProjectDeveloper",
    "arch":     "SoftwareArchitect",
    "sec":      "SecuritySpecialist",
    "devops":   "DevOpsEngineer",
    "fe":       "FrontendDev",
    "be":       "BackendDev",
    "qa":       "Tester",
    "reporter": "Reporter",
}

# PM quản lý sequence nào (theo slug)
PM_MANAGES: list[str] = ["planner", "ba", "uiux", "pd", "reporter"]

# PD quản lý sequence nào (theo slug)
PD_MANAGES: list[str] = ["arch", "sec", "devops", "fe", "be", "qa"]


class AppConfig(ProviderConfig):
    needs_writing: bool = Field(default=True)
    max_retries: int = Field(default=3)
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="console")
    streaming_enabled: bool = Field(default=True)
    mcp_enabled: bool = Field(default=False)
    mcp_config_file: str = Field(default="")
    skills_enabled: bool = Field(default=False)
    skill_names: list[str] = Field(default_factory=list)

    # --- Role bot này đảm nhận (slug: pm/ba/planner/...) ---
    bot_role: str = Field(default="pm")

    # --- Token của từng role bot ---
    token_pm: str = Field(default="")
    token_planner: str = Field(default="")
    token_ba: str = Field(default="")
    token_uiux: str = Field(default="")
    token_pd: str = Field(default="")
    token_arch: str = Field(default="")
    token_sec: str = Field(default="")
    token_devops: str = Field(default="")
    token_fe: str = Field(default="")
    token_be: str = Field(default="")
    token_qa: str = Field(default="")
    token_reporter: str = Field(default="")

    # --- Username (@handle) của từng role bot trên Telegram ---
    username_pm: str = Field(default="")
    username_planner: str = Field(default="")
    username_ba: str = Field(default="")
    username_uiux: str = Field(default="")
    username_pd: str = Field(default="")
    username_arch: str = Field(default="")
    username_sec: str = Field(default="")
    username_devops: str = Field(default="")
    username_fe: str = Field(default="")
    username_be: str = Field(default="")
    username_qa: str = Field(default="")
    username_reporter: str = Field(default="")

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

    def get_token(self, role_slug: str) -> str:
        """Lấy token của role theo slug."""
        return getattr(self, f"token_{role_slug}", "")

    def get_username(self, role_slug: str) -> str:
        """Lấy @username của role theo slug. Trả về @slug nếu chưa set."""
        val = getattr(self, f"username_{role_slug}", "")
        return val or f"{role_slug}_bot"

    def get_mention(self, role_slug: str) -> str:
        """Trả về @mention string để dùng trong tin nhắn Telegram."""
        username = self.get_username(role_slug)
        return f"@{username}" if not username.startswith("@") else username

    def get_role_name(self, role_slug: str) -> str:
        """Lấy role_name đầy đủ từ slug."""
        return ROLE_SLUG_TO_NAME.get(role_slug, role_slug)

    def get_my_token(self) -> str:
        """Token của bot này."""
        return self.get_token(self.bot_role)

    def manages(self) -> list[str]:
        """Danh sách slug các role mà bot này orchestrate."""
        if self.bot_role == "pm":
            return PM_MANAGES
        if self.bot_role == "pd":
            return PD_MANAGES
        return []


def get_config() -> AppConfig:
    return AppConfig()

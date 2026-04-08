from __future__ import annotations

from roles.base_role import BaseRole


class BackendDev(BaseRole):
    role_name: str = "BackendDev"
    mention: str = "/be"
    description: str = (
        "Backend Developer — builds API endpoints, database schema, "
        "business logic, authentication, and server-side performance."
    )
    skill_file: str = "backend_skill.md"
    extra_skills: list[str] = ["postgres_best_practices_skill.md", "tool_design_skill.md"]
    api_docs: list[str] = ["anthropic", "fastapi", "pydantic", "pydantic_settings", "aiohttp", "structlog"]

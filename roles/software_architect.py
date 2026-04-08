from __future__ import annotations

from roles.base_role import BaseRole


class SoftwareArchitect(BaseRole):
    role_name: str = "SoftwareArchitect"
    mention: str = "/arch"
    description: str = (
        "Software Architect — designs the overall system architecture, "
        "selects the tech stack, and defines module boundaries and integration patterns."
    )
    skill_file: str = "architect_skill.md"
    extra_skills: list[str] = ["multiagent_patterns_skill.md", "memory_systems_skill.md", "context_compression_skill.md"]
    api_docs: list[str] = ["anthropic", "fastapi", "pydantic", "pydantic_settings"]

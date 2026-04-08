from __future__ import annotations

from roles.base_role import BaseRole


class FrontendDev(BaseRole):
    role_name: str = "FrontendDev"
    mention: str = "/fe"
    description: str = (
        "Frontend Developer — implements UI components, state management, "
        "API integration, and responsive design per design spec."
    )
    skill_file: str = "frontend_skill.md"
    extra_skills: list[str] = ["react_best_practices_skill.md", "web_design_guidelines_skill.md"]

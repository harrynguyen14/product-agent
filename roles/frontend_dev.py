from __future__ import annotations

from roles.base_role import BaseRole


class FrontendDev(BaseRole):
    role_name: str = "FrontendDev"
    mention: str = "/fe"
    description: str = (
        "Frontend Developer — implement UI components, state management, "
        "API integration và responsive design theo design spec."
    )
    skill_file: str = "frontend_skill.md"

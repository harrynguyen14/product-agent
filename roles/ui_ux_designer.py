from __future__ import annotations

from roles.base_role import BaseRole


class UIUXDesigner(BaseRole):
    role_name: str = "UIUXDesigner"
    mention: str = "/uiux"
    description: str = (
        "UI/UX Designer — designs user interfaces and experiences, "
        "creates wireframes, design systems, and UX guidelines."
    )
    skill_file: str = "uiux_skill.md"

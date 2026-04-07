from __future__ import annotations

from roles.base_role import BaseRole


class UIUXDesigner(BaseRole):
    role_name: str = "UIUXDesigner"
    mention: str = "/uiux"
    description: str = (
        "UI/UX Designer — thiết kế giao diện người dùng và trải nghiệm, "
        "tạo wireframes, design system và UX guidelines."
    )
    skill_file: str = "uiux_skill.md"

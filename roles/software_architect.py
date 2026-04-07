from __future__ import annotations

from roles.base_role import BaseRole


class SoftwareArchitect(BaseRole):
    role_name: str = "SoftwareArchitect"
    mention: str = "/arch"
    description: str = (
        "Software Architect — thiết kế kiến trúc hệ thống tổng thể, "
        "chọn tech stack, định nghĩa module boundaries và integration patterns."
    )
    skill_file: str = "architect_skill.md"

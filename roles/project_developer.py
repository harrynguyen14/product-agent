from __future__ import annotations

from roles.base_role import BaseRole


class ProjectDeveloper(BaseRole):
    role_name: str = "ProjectDeveloper"
    mention: str = "/pd"
    description: str = (
        "Project Developer (Tech Lead) — manages the technical team, assigns tasks to developers, "
        "supervises quality at each step, and reports consolidated results to PM."
    )
    skill_file: str = "project_developer_skill.md"

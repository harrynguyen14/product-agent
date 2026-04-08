from __future__ import annotations

from roles.base_role import BaseRole


class Reporter(BaseRole):
    role_name: str = "Reporter"
    mention: str = "/report"
    description: str = (
        "Reporter — synthesizes outputs from all roles into a complete, "
        "clear, and readable project document for stakeholders. Responds in Vietnamese."
    )
    skill_file: str = "reporter_skill.md"

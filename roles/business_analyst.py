from __future__ import annotations

from roles.base_role import BaseRole


class BusinessAnalyst(BaseRole):
    role_name: str = "BusinessAnalyst"
    mention: str = "/ba"
    description: str = (
        "Business Analyst — analyzes requirements, writes User Stories, "
        "Acceptance Criteria, and functional specifications for the project."
    )
    skill_file: str = "ba_skill.md"

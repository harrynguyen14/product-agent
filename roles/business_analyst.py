from __future__ import annotations

from roles.base_role import BaseRole


class BusinessAnalyst(BaseRole):
    role_name: str = "BusinessAnalyst"
    mention: str = "/ba"
    description: str = (
        "Business Analyst — phân tích nghiệp vụ, viết User Stories, "
        "Acceptance Criteria và functional specification cho dự án."
    )
    skill_file: str = "ba_skill.md"

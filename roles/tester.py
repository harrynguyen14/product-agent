from __future__ import annotations

from roles.base_role import BaseRole


class Tester(BaseRole):
    role_name: str = "Tester"
    mention: str = "/qa"
    description: str = (
        "Tester (QA Engineer) — lập test plan, thiết kế test cases, "
        "báo cáo bugs và đảm bảo chất lượng phần mềm."
    )
    skill_file: str = "tester_skill.md"

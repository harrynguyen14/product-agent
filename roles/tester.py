from __future__ import annotations

from roles.base_role import BaseRole


class Tester(BaseRole):
    role_name: str = "Tester"
    mention: str = "/qa"
    description: str = (
        "Tester (QA Engineer) — creates test plans, designs test cases, "
        "reports bugs, and ensures software quality."
    )
    skill_file: str = "tester_skill.md"
    extra_skills: list[str] = ["agent_evaluation_skill.md"]

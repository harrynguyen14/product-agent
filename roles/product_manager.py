from __future__ import annotations

from roles.base_role import BaseRole


class ProductManager(BaseRole):
    role_name: str = "ProductManager"
    mention: str = "/pm"
    description: str = (
        "Product Manager — orchestrates the project, gathers user requirements, "
        "creates plans, assigns work to the team, and reports results to the user when complete."
    )
    skill_file: str = "pm_skill.md"
    extra_skills: list[str] = ["multiagent_patterns_skill.md"]

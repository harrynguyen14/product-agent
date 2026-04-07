from __future__ import annotations

from roles.base_role import BaseRole


class DevOpsEngineer(BaseRole):
    role_name: str = "DevOpsEngineer"
    mention: str = "/devops"
    description: str = (
        "DevOps Engineer — thiết kế CI/CD pipeline, infrastructure, "
        "Docker/Kubernetes config, monitoring và deployment strategy."
    )
    skill_file: str = "devops_skill.md"

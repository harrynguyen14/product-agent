from __future__ import annotations

from roles.base_role import BaseRole


class DevOpsEngineer(BaseRole):
    role_name: str = "DevOpsEngineer"
    mention: str = "/devops"
    description: str = (
        "DevOps Engineer — designs CI/CD pipelines, infrastructure as code, "
        "Docker/Kubernetes configuration, monitoring, and deployment strategy."
    )
    skill_file: str = "devops_skill.md"
    api_docs: list[str] = ["python_dotenv", "rich", "structlog"]

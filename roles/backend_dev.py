from __future__ import annotations

from roles.base_role import BaseRole


class BackendDev(BaseRole):
    role_name: str = "BackendDev"
    mention: str = "/be"
    description: str = (
        "Backend Developer — xây dựng API endpoints, database schema, "
        "business logic, authentication và server-side performance."
    )
    skill_file: str = "backend_skill.md"

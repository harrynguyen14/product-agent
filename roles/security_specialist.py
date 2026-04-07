from __future__ import annotations

from roles.base_role import BaseRole


class SecuritySpecialist(BaseRole):
    role_name: str = "SecuritySpecialist"
    mention: str = "/sec"
    description: str = (
        "Security Specialist — review bảo mật, threat modeling (STRIDE), "
        "OWASP compliance và đề xuất security best practices."
    )
    skill_file: str = "security_skill.md"

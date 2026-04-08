from __future__ import annotations

from roles.base_role import BaseRole


class SecuritySpecialist(BaseRole):
    role_name: str = "SecuritySpecialist"
    mention: str = "/sec"
    description: str = (
        "Security Specialist — performs security reviews, threat modeling (STRIDE), "
        "OWASP compliance checks, and recommends security best practices."
    )
    skill_file: str = "security_skill.md"
    extra_skills: list[str] = ["vibesec_security_skill.md"]

from __future__ import annotations

from roles.base_role import BaseRole


class VietnameseTranslator(BaseRole):
    role_name: str = "VietnameseTranslator"
    mention: str = "/translate"
    description: str = (
        "Vietnamese Translator — translates internal English role outputs "
        "into clear, professional Vietnamese for end users."
    )
    skill_file: str = "vietnamese_translator_skill.md"
    enable_skill_selection: bool = False

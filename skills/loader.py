"""Skill loader — reads a skill .md file and returns its content as a string.

Usage in agents:
    from skills.loader import load_skill
    SYSTEM = load_skill("search_skill.md") + "\n\n" + _BASE_SYSTEM
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_SKILLS_DIR = Path(__file__).parent


@lru_cache(maxsize=None)
def load_skill(filename: str) -> str:
    """Return the full text of a skill .md file.

    Args:
        filename: bare filename, e.g. "search_skill.md"

    Returns:
        Skill content as a string, or empty string if file not found.
    """
    path = _SKILLS_DIR / filename
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()

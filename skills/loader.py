from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

_SKILLS_DIR = Path(__file__).parent
_SEARCH_ORDER = ["roles", "agents", "shared", "api_docs", "."]


@dataclass(frozen=True)
class SkillMeta:
    name: str
    description: str
    path: Path

    def summary(self) -> str:
        return f"[{self.name}] {self.description}"


def _parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end == -1:
        return {}
    block = text[3:end].strip()
    result: dict[str, str] = {}
    current_key: Optional[str] = None
    buffer: list[str] = []

    for line in block.splitlines():
        if re.match(r"^\w[\w-]*\s*:", line):
            if current_key:
                result[current_key] = " ".join(buffer).strip()
            parts = line.split(":", 1)
            current_key = parts[0].strip()
            val = parts[1].strip().lstrip("|").strip()
            buffer = [val] if val else []
        elif current_key and line.startswith("  "):
            buffer.append(line.strip())

    if current_key:
        result[current_key] = " ".join(buffer).strip()

    return result


def _find_skill_path(filename: str) -> Optional[Path]:
    candidate = _SKILLS_DIR / filename
    if candidate.exists():
        return candidate

    bare = Path(filename).name
    for folder in _SEARCH_ORDER:
        base = _SKILLS_DIR / folder
        if not base.is_dir():
            continue
        for p in base.rglob(bare):
            if p.is_file():
                return p

    return None


@lru_cache(maxsize=None)
def load_skill(filename: str) -> str:
    path = _find_skill_path(filename)
    if path is None:
        return ""
    return path.read_text(encoding="utf-8").strip()


def load_skill_by_path(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=None)
def load_api_doc(library: str) -> str:
    filename = f"{library}_api_doc.md"
    path = _SKILLS_DIR / "api_docs" / filename
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=None)
def scan_skill_metadata(subfolder: str = "shared") -> tuple[SkillMeta, ...]:
    base = _SKILLS_DIR / subfolder
    if not base.is_dir():
        return ()

    metas: list[SkillMeta] = []
    for md_path in sorted(base.rglob("*.md")):
        text = md_path.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)
        name = fm.get("name", "").strip()
        description = fm.get("description", "").strip()
        if name and description:
            metas.append(SkillMeta(name=name, description=description, path=md_path))

    return tuple(metas)


def list_skills(subfolder: Optional[str] = None) -> list[str]:
    if subfolder:
        base = _SKILLS_DIR / subfolder
        return sorted(str(p.relative_to(_SKILLS_DIR)) for p in base.rglob("*.md"))

    results = []
    for folder in _SEARCH_ORDER:
        d = _SKILLS_DIR / folder
        if d.is_dir():
            results.extend(str(p.relative_to(_SKILLS_DIR)) for p in d.rglob("*.md"))
    return sorted(results)

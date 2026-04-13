from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from core.llm_factory import LLMCallable
from skills.loader import SkillMeta, load_skill_by_path, scan_skill_metadata

logger = logging.getLogger(__name__)

_SELECTOR_PROMPT = """\
You are a skill selector. Given a task description and a list of available skills, \
select which skills are relevant to completing the task.

Available skills:
{skill_list}

Task:
{task}

Return a JSON array of skill names that are relevant to this task. \
Only include skills that would genuinely help. Return an empty array [] if none apply.
Return ONLY the JSON array, no explanation.

Example: ["frontend-dev", "fullstack-dev"]
"""


def _extract_json_array(text: str) -> list[str] | None:
    for match in re.finditer(r"\[([^\[\]]*)\]", text):
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list) and all(isinstance(i, str) for i in parsed):
                return parsed
        except json.JSONDecodeError:
            continue
    return None


async def select_skills(
    task: str,
    llm: LLMCallable,
    subfolder: str = "shared",
    max_skills: int = 3,
) -> list[SkillMeta]:
    metas = scan_skill_metadata(subfolder)
    if not metas:
        return []

    skill_list = "\n".join(f"- {m.name}: {m.description}" for m in metas)
    prompt = _SELECTOR_PROMPT.format(skill_list=skill_list, task=task)

    from langchain_core.messages import HumanMessage
    try:
        raw = await llm([HumanMessage(content=prompt)])
    except Exception:
        logger.exception("skill_selector: LLM call failed for task=%r", task[:80])
        return []

    selected_names = _extract_json_array(raw.strip())
    if selected_names is None:
        logger.warning("skill_selector: could not parse JSON array from LLM response: %r", raw[:200])
        return []

    name_to_meta = {m.name: m for m in metas}
    result = [
        name_to_meta[name]
        for name in selected_names[:max_skills]
        if name in name_to_meta
    ]
    return result


def load_selected_skills(metas: list[SkillMeta]) -> str:
    sections: list[str] = []
    for meta in metas:
        content = load_skill_by_path(meta.path)
        if content:
            sections.append(content)
    return "\n\n---\n\n".join(sections)

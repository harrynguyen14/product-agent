from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, model_validator

from actions.action import LLMAction, LLMCallable
from schemas.agent_result import AgentResult
from skills.loader import load_skill

__all__ = ["AgentResult", "BaseAgent"]


class BaseAgent(BaseModel):
    """Base agent. Subclasses implement run() and declare their own task_type.

    Skill integration:
        Set `skill_file = "your_skill.md"` in a subclass to automatically
        prepend the skill content to every system message sent to the LLM.
        The skill content teaches the LLM *how* to behave in this agent's role.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = ""
    skill_file: str = ""          # e.g. "search_skill.md" — set in each subclass
    _llm: Optional[LLMCallable] = None
    _skill_content: str = ""      # loaded once, cached on first use

    @model_validator(mode="after")
    def _set_name(self) -> "BaseAgent":
        if not self.name:
            self.name = self.__class__.__name__
        return self

    def set_llm(self, llm: LLMCallable) -> "BaseAgent":
        self._llm = llm
        return self

    def _get_system(self, base_system: str) -> str:
        """Return the full system message: skill content prepended to base_system.

        If no skill_file is set, returns base_system unchanged.
        The skill content is loaded once and cached (lru_cache in loader.py).
        """
        if not self.skill_file:
            return base_system
        if not self._skill_content:
            object.__setattr__(self, "_skill_content", load_skill(self.skill_file))
        skill = self._skill_content
        if not skill:
            return base_system
        return f"{skill}\n\n---\n\n{base_system}"

    def _make_action(self, action_cls: type[LLMAction], **kwargs) -> LLMAction:
        if self._llm is None:
            raise RuntimeError(f"[{self.name}] LLM has not been injected")
        action = action_cls(**kwargs)
        action.set_llm(self._llm)
        return action

    async def run(self, task: dict, upstream: dict[str, Any]) -> AgentResult:
        raise NotImplementedError

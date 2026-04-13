from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

from core.llm_factory import LLMCallable
from skills.loader import load_api_doc, load_skill

__all__ = ["BaseRole"]


class BaseRole(BaseModel):
    """Persona-based role trong multi-agent Telegram system.

    Mỗi subclass khai báo:
        role_name  : Tên hiển thị (e.g. "ProductManager")
        mention    : Slug dùng trong config (e.g. "pm")
        skill_file : Markdown file trong skills/ định nghĩa hành vi
        description: Mô tả ngắn nhiệm vụ
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    role_name: str = ""
    mention: str = ""
    description: str = ""
    skill_file: str = ""
    extra_skills: list[str] = Field(default_factory=list)
    api_docs: list[str] = Field(default_factory=list)
    enable_skill_selection: bool = True
    max_dynamic_skills: int = 3
    history_window: int = 10

    _llm: Optional[LLMCallable] = PrivateAttr(default=None)
    _skill_content: str = PrivateAttr(default="")
    _history: list[dict[str, str]] = PrivateAttr(default_factory=list)

    @model_validator(mode="after")
    def _set_defaults(self) -> "BaseRole":
        if not self.role_name:
            self.role_name = self.__class__.__name__
        return self

    def set_llm(self, llm: LLMCallable) -> "BaseRole":
        self._llm = llm
        return self

    def _build_static_prompt(self) -> str:
        base = f"You are {self.role_name}. {self.description}"

        if not self.skill_file:
            role_skill = base
        else:
            if not self._skill_content:
                object.__setattr__(self, "_skill_content", load_skill(self.skill_file))
            skill = self._skill_content
            role_skill = f"{skill}\n\n---\n\n{base}" if skill else base

        for extra_file in self.extra_skills:
            extra_content = load_skill(extra_file)
            if extra_content:
                role_skill = f"{role_skill}\n\n---\n\n{extra_content}"

        if self.api_docs:
            doc_sections = []
            for lib in self.api_docs:
                doc = load_api_doc(lib)
                if doc:
                    doc_sections.append(f"## {lib.upper()} API REFERENCE\n\n{doc}")
            if doc_sections:
                docs_block = "\n\n---\n\n".join(doc_sections)
                role_skill = f"{role_skill}\n\n---\n\n## Library Documentation\n\n{docs_block}"

        return role_skill

    async def _build_dynamic_prompt(self, task: str) -> str:
        static = self._build_static_prompt()
        if not self.enable_skill_selection or self._llm is None:
            return static

        from skills.skill_selector import load_selected_skills, select_skills
        selected = await select_skills(
            task=task,
            llm=self._llm,
            max_skills=self.max_dynamic_skills,
        )
        if not selected:
            return static

        dynamic_content = load_selected_skills(selected)
        return f"{static}\n\n---\n\n## Dynamically Loaded Skills\n\n{dynamic_content}"

    def add_to_history(self, role: str, content: str) -> None:
        self._history.append({"role": role, "content": content})

    def clear_history(self) -> None:
        object.__setattr__(self, "_history", [])

    def trim_history(self, keep: Optional[int] = None) -> None:
        n = keep if keep is not None else self.history_window
        if len(self._history) > n:
            object.__setattr__(self, "_history", self._history[-n:])

    async def respond(self, user_message: str, context: str = "") -> str:
        if self._llm is None:
            raise RuntimeError(f"[{self.role_name}] LLM not injected")
        return await self._respond_plain(user_message, context)

    async def _respond_plain(self, user_message: str, context: str) -> str:
        import asyncio
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        system = await self._build_dynamic_prompt(user_message)
        messages = [SystemMessage(content=system)]

        if context:
            messages.append(SystemMessage(content=f"## Context from previous roles:\n{context}"))

        for entry in self._history[-self.history_window:]:
            if entry["role"] == "user":
                messages.append(HumanMessage(content=entry["content"]))
            else:
                messages.append(AIMessage(content=entry["content"]))

        messages.append(HumanMessage(content=user_message))

        response = await asyncio.wait_for(self._llm(messages), timeout=120)

        self.add_to_history("user", user_message)
        self.add_to_history("assistant", response)

        return response

    async def run_task(self, instruction: str, upstream_context: str = "") -> str:
        return await self.respond(instruction, context=upstream_context)

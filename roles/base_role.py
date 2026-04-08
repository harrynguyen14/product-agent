from __future__ import annotations

from typing import Any, Optional

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field, model_validator

from actions.action import LLMAction, LLMCallable
from skills.loader import load_api_doc, load_skill

__all__ = ["BaseRole"]


class BaseRole(BaseModel):
    """Persona-based role that participates in a multi-agent conversation.

    Each subclass declares:
        role_name   : Display name shown in Discord messages (e.g. "ProductManager")
        mention     : Slash-command trigger in task channels (e.g. "/pm")
        skill_file  : Markdown file in skills/ that defines how this role behaves
        description : One-line description of responsibilities

    Skill loading — two layers:
        static  : skill_file + extra_skills — always loaded at prompt build time
        dynamic : select_skills() — LLM picks relevant shared/ skills just-in-time
                  based on the current task. Disabled when enable_skill_selection=False.
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
    max_react_steps: int = 6
    history_window: int = 10
    react_history_window: int = 6

    _llm: Optional[LLMCallable] = None
    _skill_content: str = ""
    _history: list[dict[str, str]] = Field(default_factory=list)
    _tools: list[BaseTool] = Field(default_factory=list)

    @model_validator(mode="after")
    def _set_defaults(self) -> "BaseRole":
        if not self.role_name:
            self.role_name = self.__class__.__name__
        return self

    def set_llm(self, llm: LLMCallable) -> "BaseRole":
        self._llm = llm
        return self

    def set_tools(self, tools: list[BaseTool]) -> "BaseRole":
        object.__setattr__(self, "_tools", list(tools))
        return self

    def _build_static_prompt(self) -> str:
        base = (
            f"You are {self.role_name}. {self.description}"
        )
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

        if self._tools:
            search_skill = load_skill("role_search_skill.md")
            if search_skill:
                return f"{search_skill}\n\n---\n\n{role_skill}"

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

        if self._tools:
            return await self._respond_with_tools(user_message, context)
        return await self._respond_plain(user_message, context)

    async def _respond_with_tools(self, user_message: str, context: str) -> str:
        from actions.action import LLMAction
        from actions.react_loop import ReActLoop

        action = LLMAction()
        action.set_llm(self._llm)

        history_str = ""
        if self._history:
            history_str = "\n".join(
                f"{'User' if e['role'] == 'user' else self.role_name}: {e['content']}"
                for e in self._history[-self.react_history_window:]
            )

        full_context = "\n\n".join(filter(None, [
            f"## Conversation history\n{history_str}" if history_str else "",
            f"## Context from previous roles\n{context}" if context else "",
        ]))

        system_prompt = await self._build_dynamic_prompt(user_message)

        loop = ReActLoop(
            action=action,
            tools=self._tools,
            max_steps=self.max_react_steps,
            system_msg=system_prompt,
        )

        result = await loop.run(goal=user_message, context=full_context)
        response = result.answer

        self.add_to_history("user", user_message)
        self.add_to_history("assistant", response)

        return response

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

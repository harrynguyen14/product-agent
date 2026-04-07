from __future__ import annotations

from typing import Any, Optional

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, model_validator

from actions.action import LLMAction, LLMCallable
from skills.loader import load_skill

__all__ = ["BaseRole"]


class BaseRole(BaseModel):
    """Persona-based role that participates in a multi-agent conversation.

    Each subclass declares:
        role_name   : Display name shown in Discord messages (e.g. "ProductManager")
        mention     : Slash-command trigger in task channels (e.g. "/pm")
        skill_file  : Markdown file in skills/ that defines how this role behaves
        description : One-line description of responsibilities

    Unlike the task-based BaseAgent, BaseRole is persona-centric — it maintains
    a conversation history and can be "called" via a slash command in a Discord
    task channel.

    When tools are injected via set_tools(), respond() automatically switches to
    a ReAct loop (Thought → Action → Observation) so the role can search the web
    or call other tools before producing its final answer.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    role_name: str = ""
    mention: str = ""
    description: str = ""
    skill_file: str = ""
    max_react_steps: int = 6  # max ReAct cycles when tools are available

    _llm: Optional[LLMCallable] = None
    _skill_content: str = ""
    _history: list[dict[str, str]] = []    # [{"role": "user"|"assistant", "content": "..."}]
    _tools: list[BaseTool] = []

    @model_validator(mode="after")
    def _set_defaults(self) -> "BaseRole":
        if not self.role_name:
            self.role_name = self.__class__.__name__
        return self

    # ------------------------------------------------------------------
    # LLM injection
    # ------------------------------------------------------------------

    def set_llm(self, llm: LLMCallable) -> "BaseRole":
        self._llm = llm
        return self

    def set_tools(self, tools: list[BaseTool]) -> "BaseRole":
        """Inject tools so respond() uses a ReAct loop instead of a plain LLM call."""
        object.__setattr__(self, "_tools", list(tools))
        return self

    # ------------------------------------------------------------------
    # Skill / system message
    # ------------------------------------------------------------------

    def _get_system_prompt(self) -> str:
        base = (
            f"Bạn là {self.role_name}. {self.description}\n\n"
            "Hãy trả lời bằng tiếng Việt, ngắn gọn và chuyên nghiệp."
        )
        if not self.skill_file:
            role_skill = base
        else:
            if not self._skill_content:
                object.__setattr__(self, "_skill_content", load_skill(self.skill_file))
            skill = self._skill_content
            role_skill = f"{skill}\n\n---\n\n{base}" if skill else base

        # When tools are available, prepend the search guidance skill
        if self._tools:
            search_skill = load_skill("role_search_skill.md")
            if search_skill:
                return f"{search_skill}\n\n---\n\n{role_skill}"

        return role_skill

    # ------------------------------------------------------------------
    # Conversation history
    # ------------------------------------------------------------------

    def add_to_history(self, role: str, content: str) -> None:
        self._history.append({"role": role, "content": content})

    def clear_history(self) -> None:
        object.__setattr__(self, "_history", [])

    # ------------------------------------------------------------------
    # Core respond method
    # ------------------------------------------------------------------

    async def respond(self, user_message: str, context: str = "") -> str:
        """Generate a response to user_message.

        When tools are available, runs a ReAct loop so the role can search
        the web (or call other tools) before producing its final answer.
        Without tools, falls back to a plain multi-turn LLM call.

        Args:
            user_message: The message directed at this role.
            context:      Optional upstream context (outputs from previous roles).
        """
        if self._llm is None:
            raise RuntimeError(f"[{self.role_name}] LLM not injected")

        if self._tools:
            return await self._respond_with_tools(user_message, context)
        return await self._respond_plain(user_message, context)

    async def _respond_with_tools(self, user_message: str, context: str) -> str:
        """ReAct loop: Thought → Action (tool call) → Observation → … → Final Answer."""
        from actions.action import LLMAction
        from actions.react_loop import ReActLoop

        action = LLMAction()
        action.set_llm(self._llm)

        # Build rich context: role history + upstream context
        history_str = ""
        if self._history:
            history_str = "\n".join(
                f"{'User' if e['role'] == 'user' else self.role_name}: {e['content']}"
                for e in self._history[-6:]
            )

        full_context = "\n\n".join(filter(None, [
            f"## Conversation history\n{history_str}" if history_str else "",
            f"## Context từ các roles trước\n{context}" if context else "",
        ]))

        loop = ReActLoop(
            action=action,
            tools=self._tools,
            max_steps=self.max_react_steps,
            system_msg=self._get_system_prompt(),
        )

        result = await loop.run(goal=user_message, context=full_context)
        response = result.answer

        # Update history
        self.add_to_history("user", user_message)
        self.add_to_history("assistant", response)

        return response

    async def _respond_plain(self, user_message: str, context: str) -> str:
        """Plain multi-turn LLM call (no tools)."""
        import asyncio
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

        system = self._get_system_prompt()
        messages = [SystemMessage(content=system)]

        if context:
            messages.append(SystemMessage(content=f"## Context từ các roles trước:\n{context}"))

        for entry in self._history[-10:]:
            if entry["role"] == "user":
                messages.append(HumanMessage(content=entry["content"]))
            else:
                messages.append(AIMessage(content=entry["content"]))

        messages.append(HumanMessage(content=user_message))

        response = await asyncio.wait_for(self._llm(messages), timeout=120)

        self.add_to_history("user", user_message)
        self.add_to_history("assistant", response)

        return response

    # ------------------------------------------------------------------
    # Convenience: run a structured task (used by flows/graph)
    # ------------------------------------------------------------------

    async def run_task(self, instruction: str, upstream_context: str = "") -> str:
        """Execute a specific task instruction and return the output."""
        return await self.respond(instruction, context=upstream_context)

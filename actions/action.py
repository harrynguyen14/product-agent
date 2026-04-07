from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Optional, Protocol, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, model_validator


class LLMCallable(Protocol):
    async def __call__(self, messages: list[BaseMessage]) -> str: ...


class ActionContext(TypedDict, total=False):
    input: Any
    memory: Any
    tools: dict[str, Callable]
    config: dict
    state: dict


# ---------------------------------------------------------------------------
# Base — shared config, no LLM requirement (ISP: only carry what you need)
# ---------------------------------------------------------------------------

class Action(BaseModel):
    """Base action. Subclass PureAction (no LLM) or LLMAction (requires LLM)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = ""
    desc: str = ""
    prefix: str = ""

    @model_validator(mode="after")
    def _set_default_name(self) -> "Action":
        if not self.name:
            self.name = self.__class__.__name__
        return self

    async def run(self, ctx: ActionContext) -> Any:
        raise NotImplementedError(f"Action '{self.name}' has not implemented run()")

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"


# ---------------------------------------------------------------------------
# PureAction — no LLM needed (pure Python / tool calls)
# ---------------------------------------------------------------------------

class PureAction(Action):
    """Action that does not require an LLM."""


# ---------------------------------------------------------------------------
# LLMAction — requires an injected LLM callable (DIP: depends on abstraction)
# ---------------------------------------------------------------------------

class LLMAction(Action):
    """Action that requires an injected LLM callable."""

    max_retries: int = 2
    timeout: int = 60

    _llm: Optional[LLMCallable] = None

    def set_llm(self, llm: LLMCallable) -> "LLMAction":
        self._llm = llm
        return self

    def set_prefix(self, prefix: str) -> "LLMAction":
        self.prefix = prefix
        return self

    async def _call_llm(self, messages: list[BaseMessage]) -> str:
        if self._llm is None:
            raise RuntimeError(f"[{self.name}] LLM has not been injected")

        last_err: Exception = RuntimeError("unknown")
        for attempt in range(self.max_retries + 1):
            try:
                return await asyncio.wait_for(
                    self._llm(messages),
                    timeout=self.timeout,
                )
            except Exception as e:
                last_err = e
                if attempt >= self.max_retries:
                    raise RuntimeError(
                        f"[{self.name}] LLM call failed after {self.max_retries} retries: {e}"
                    ) from e
                await asyncio.sleep(0.5 * (attempt + 1))

        raise last_err

    async def aask(
        self,
        prompt: str,
        system_msg: Optional[str] = None,
    ) -> str:
        messages: list[BaseMessage] = []
        sys = system_msg or self.prefix
        if sys:
            messages.append(SystemMessage(content=sys))
        messages.append(HumanMessage(content=prompt))
        return await self._call_llm(messages)

    async def aask_messages(self, messages: list[BaseMessage]) -> str:
        return await self._call_llm(messages)

    async def aask_json(self, prompt: str) -> dict:
        """Call LLM and parse response as JSON. Raises ValueError on parse failure."""
        raw = await self.aask(prompt)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"[{self.name}] Response is not valid JSON: {e}\nRaw output:\n{raw}"
            ) from e

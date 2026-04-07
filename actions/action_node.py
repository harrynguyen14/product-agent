from __future__ import annotations

from typing import Any, Optional, Type, Union

from pydantic import BaseModel, ConfigDict

from actions.action import LLMAction


class ActionNode(BaseModel):
    """Wraps an LLMAction and optionally validates the response against a Pydantic schema.

    If schema_cls is provided the response MUST parse successfully — no silent fallback.
    Callers that want plain text output should leave schema_cls=None.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = ""
    schema_cls: Optional[Type[BaseModel]] = None
    _action: Optional[LLMAction] = None

    def set_action(self, action: LLMAction) -> "ActionNode":
        self._action = action
        return self

    def set_schema(self, schema_cls: Type[BaseModel]) -> "ActionNode":
        self.schema_cls = schema_cls
        return self

    async def run(self, prompt: str, system_msg: Optional[str] = None) -> Union[BaseModel, str]:
        if self._action is None:
            raise RuntimeError(f"[{self.name}] Action not set on ActionNode")

        if self.schema_cls is None:
            return await self._action.aask(prompt, system_msg=system_msg)

        schema_fields = list(self.schema_cls.model_fields.keys())
        json_prompt = (
            f"{prompt}\n\n"
            f"Respond ONLY with a valid JSON object with these fields: {schema_fields}"
        )
        # aask_json already raises ValueError on parse failure — propagate it
        raw_json = await self._action.aask_json(json_prompt)
        try:
            return self.schema_cls(**raw_json)
        except Exception as e:
            raise ValueError(
                f"[{self.name}] Response does not match schema {self.schema_cls.__name__}: {e}"
            ) from e

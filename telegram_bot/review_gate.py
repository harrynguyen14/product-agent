from __future__ import annotations

import asyncio
from typing import Optional


class TelegramReviewGate:
    """Bridges the planner's review step with a Telegram chat.

    Usage:
        gate = TelegramReviewGate()
        # pass gate to Planner, then AskReview calls gate.wait()
        # when user replies in Telegram, bot calls gate.resolve(text)
    """

    def __init__(self) -> None:
        self._future: Optional[asyncio.Future[str]] = None

    @property
    def is_waiting(self) -> bool:
        return self._future is not None and not self._future.done()

    def arm(self) -> None:
        """Prepare a new Future for the next review round."""
        loop = asyncio.get_event_loop()
        self._future = loop.create_future()

    def resolve(self, text: str) -> None:
        """Called by the bot when the user replies."""
        if self._future and not self._future.done():
            self._future.set_result(text)

    async def wait(self, timeout: float = 600.0) -> str:
        """Block until the user replies or timeout (seconds)."""
        if self._future is None:
            raise RuntimeError("Gate was not armed before waiting.")
        return await asyncio.wait_for(self._future, timeout=timeout)

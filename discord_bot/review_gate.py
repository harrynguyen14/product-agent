from __future__ import annotations

import asyncio
from typing import Optional


class DiscordReviewGate:
    """Async gate that bridges the planning loop with a Discord user reply.

    Usage:
        gate = DiscordReviewGate()
        gate.arm()
        # ... bot sends plan to Discord channel ...
        reply = await gate.wait(timeout=600)
        # ... Discord handler calls gate.resolve(user_text) when user replies ...
    """

    def __init__(self) -> None:
        self._future: Optional[asyncio.Future[str]] = None

    def arm(self) -> None:
        """Prepare a fresh Future to wait on."""
        loop = asyncio.get_event_loop()
        self._future = loop.create_future()

    def resolve(self, text: str) -> None:
        """Called by the Discord message handler when the user replies."""
        if self._future and not self._future.done():
            self._future.set_result(text)

    async def wait(self, timeout: float = 600) -> str:
        """Block until resolved or timeout (seconds). Returns user text."""
        if self._future is None:
            raise RuntimeError("DiscordReviewGate.arm() must be called before wait()")
        return await asyncio.wait_for(self._future, timeout=timeout)

    @property
    def is_armed(self) -> bool:
        return self._future is not None and not self._future.done()

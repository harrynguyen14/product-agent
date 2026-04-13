from __future__ import annotations

import asyncio
from typing import Optional

ACCEPT_WORDS = {"ok", "yes", "y", "tiếp", "tiep", "đồng ý", "dong y", "accept", "oke", "ok!"}


class HumanGate:
    """Async gate — suspends execution until the user replies.

    Usage:
        gate = HumanGate()
        gate.arm()
        reply = await gate.wait(timeout=300)   # blocks until resolve()
        gate.resolve("ok")                      # called by message handler
    """

    def __init__(self) -> None:
        self._future: Optional[asyncio.Future[str]] = None

    @property
    def is_waiting(self) -> bool:
        return self._future is not None and not self._future.done()

    def arm(self) -> None:
        """Prepare a new future. Must be called before wait()."""
        loop = asyncio.get_event_loop()
        self._future = loop.create_future()

    def resolve(self, text: str) -> None:
        """Called by the message handler when the user sends a reply."""
        if self._future and not self._future.done():
            self._future.set_result(text.strip())

    async def wait(self, timeout: float = 600.0) -> str:
        """Wait for user reply. Raises asyncio.TimeoutError on timeout."""
        if self._future is None:
            raise RuntimeError("Gate not armed — call arm() first")
        return await asyncio.wait_for(asyncio.shield(self._future), timeout=timeout)

    def is_accepted(self, reply: str) -> bool:
        """True if the reply is an acceptance word."""
        return reply.strip().lower() in ACCEPT_WORDS

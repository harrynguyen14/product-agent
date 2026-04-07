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


class RoleReviewGate:
    """Gate that pauses execution after each role completes and waits for human input.

    The bot calls arm() + wait() after posting a role_done message.
    The on_message handler calls resolve(text) when the user replies.

    resolve() returns:
        (accepted=True,  feedback="")        — user typed an accept word
        (accepted=False, feedback="<text>")  — user typed feedback
    """

    ACCEPT_WORDS = {"ok", "yes", "y", "tiếp", "tiếp tục", "next", "accept",
                    "chấp nhận", "đồng ý", "approved", "✅", "👍"}

    def __init__(self) -> None:
        self._future: Optional[asyncio.Future[str]] = None

    def arm(self) -> None:
        loop = asyncio.get_event_loop()
        self._future = loop.create_future()

    def resolve(self, text: str) -> None:
        if self._future and not self._future.done():
            self._future.set_result(text)

    async def wait(self, timeout: float = 300) -> tuple[bool, str]:
        """Wait for user reply. Returns (accepted, feedback)."""
        if self._future is None:
            raise RuntimeError("RoleReviewGate.arm() must be called before wait()")
        try:
            text = await asyncio.wait_for(self._future, timeout=timeout)
        except asyncio.TimeoutError:
            # Treat timeout as auto-accept to avoid blocking forever
            return True, ""
        accepted = text.strip().lower() in self.ACCEPT_WORDS
        feedback = "" if accepted else text.strip()
        return accepted, feedback

    @property
    def is_armed(self) -> bool:
        return self._future is not None and not self._future.done()

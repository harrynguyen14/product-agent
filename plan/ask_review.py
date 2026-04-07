from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from telegram_bot.review_gate import TelegramReviewGate


class ReviewConst:
    CONFIRM_WORDS = ["confirm", "continue", "c", "yes", "y"]
    EXIT_WORDS    = ["exit", "quit", "q"]

    PLAN_REVIEW_INSTRUCTION = (
        "Review the plan above.\n"
        "- To accept: type 'yes' / 'confirm' / 'y'\n"
        "- To request changes or provide more info: type your feedback\n"
        "- To exit: type 'exit'"
    )


class AskReview:
    """Prompt the user to review a plan and return (user_input, confirmed).

    When a TelegramReviewGate is provided the review waits for a Telegram
    reply instead of reading from stdin.
    """

    def __init__(self, gate: Optional["TelegramReviewGate"] = None) -> None:
        self._gate = gate

    async def run(self, plan_text: str) -> Tuple[str, bool]:
        # --- Telegram path ---
        if self._gate is not None:
            self._gate.arm()
            rsp = await self._gate.wait()
            rsp = rsp.strip()
            if rsp.lower() in ReviewConst.EXIT_WORDS:
                raise SystemExit("User exited the planning loop.")
            confirmed = rsp.lower() in ReviewConst.CONFIRM_WORDS or ReviewConst.CONFIRM_WORDS[0] in rsp.lower()
            return rsp, confirmed

        # --- Terminal path ---
        if not sys.stdin.isatty():
            return "yes", True

        print("\n" + "=" * 60)
        print("Current Plan:")
        print(plan_text)
        print("=" * 60)
        print(ReviewConst.PLAN_REVIEW_INSTRUCTION)
        sys.stdout.flush()

        try:
            rsp = input("\nYour review: ").strip()
        except (EOFError, OSError):
            return "yes", True

        if rsp.lower() in ReviewConst.EXIT_WORDS:
            raise SystemExit("User exited the planning loop.")

        confirmed = rsp.lower() in ReviewConst.CONFIRM_WORDS or ReviewConst.CONFIRM_WORDS[0] in rsp.lower()
        return rsp, confirmed

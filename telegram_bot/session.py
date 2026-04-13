from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Optional

from config.settings import AppConfig
from telegram_bot.review_gate import HumanGate


@dataclass
class ChatSession:
    """Trạng thái mỗi chat/group mà bot tham gia."""
    chat_id: int
    config: AppConfig

    # Gate chờ user confirm trước khi chạy role (PM/PD)
    gate: HumanGate = field(default_factory=HumanGate)

    # Gate chờ reply từ role bot sau khi mention (PM/PD)
    role_reply_gate: HumanGate = field(default_factory=HumanGate)

    # Slug của role đang chờ reply (để validate đúng bot reply)
    expect_reply_from: Optional[str] = field(default=None)

    # Task asyncio đang chạy pipeline
    active_task: Optional[asyncio.Task] = field(default=None)

    def is_busy(self) -> bool:
        return self.active_task is not None and not self.active_task.done()


_sessions: dict[int, ChatSession] = {}


def get_session(chat_id: int, config: AppConfig) -> ChatSession:
    if chat_id not in _sessions:
        _sessions[chat_id] = ChatSession(chat_id=chat_id, config=config)
    return _sessions[chat_id]

from __future__ import annotations

import asyncio
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from telegram import Update, constants
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config.settings import AppConfig, get_config
from config.provider_config import LLMProvider
from core.runner import EnvironmentRunner
from infrastructure.logging import get_logger
from telegram_bot.formatters import (
    export_report_markdown,
    format_error,
    format_plan,
    format_telegram_summary,
    format_thinking,
    split_long_message,
)
from telegram_bot.review_gate import TelegramReviewGate

logger = get_logger("telegram.bot")


class ChatSession:
    def __init__(self, chat_id: int, config: AppConfig):
        self.chat_id = chat_id
        self.config = config
        self.active_task: Optional[asyncio.Task] = None
        self.review_gate: TelegramReviewGate = TelegramReviewGate()


_sessions: dict[int, ChatSession] = {}


def _get_session(chat_id: int, config: AppConfig) -> ChatSession:
    if chat_id not in _sessions:
        _sessions[chat_id] = ChatSession(chat_id, config)
    return _sessions[chat_id]


async def _tg_call(coro, retries: int = 3):
    from telegram.error import RetryAfter
    last_err: Exception = Exception("no attempts")
    for attempt in range(retries):
        try:
            return await coro
        except RetryAfter as e:
            last_err = e
            await asyncio.sleep(e.retry_after + 1)
        except Exception:
            raise
    raise last_err


async def _send(update: Update, text: str, parse_mode: str = "HTML") -> None:
    for chunk in split_long_message(text):
        await _tg_call(update.effective_chat.send_message(chunk, parse_mode=parse_mode))


async def _run_pipeline(update: Update, session: ChatSession, problem: str) -> None:
    runner = EnvironmentRunner(config=session.config, review_gate=session.review_gate)
    status_msg_id: Optional[int] = None
    _last_edit_time = 0.0

    try:
        status_msg = await _tg_call(
            update.effective_chat.send_message("⏳ <b>Pipeline starting...</b>", parse_mode="HTML")
        )
        status_msg_id = status_msg.message_id

        final_state: dict = {}

        async for event in runner.stream(problem):
            etype = event["type"]

            if etype == "role_start":
                role = event.get("role", "")
                label = format_thinking(role)
                now = asyncio.get_event_loop().time()
                if now - _last_edit_time >= 2.0:
                    try:
                        await _tg_call(
                            update.effective_chat.edit_message_text(
                                label, message_id=status_msg_id, parse_mode="HTML"
                            )
                        )
                        _last_edit_time = asyncio.get_event_loop().time()
                    except Exception:
                        pass

            elif etype == "plan_ready":
                # plan is now a pre-formatted string from Planner._format_plan()
                plan_text = event.get("plan", "")
                if plan_text:
                    await _send(update, f"📋 <b>Kế hoạch nghiên cứu:</b>\n<pre>{plan_text}</pre>")
                    await _send(
                        update,
                        "👆 <b>Kế hoạch trên cần bạn xác nhận.</b>\n"
                        "• Gõ <code>yes</code> / <code>y</code> để chấp nhận\n"
                        "• Gõ góp ý để chỉnh sửa\n"
                        "• Gõ <code>exit</code> để huỷ",
                    )

            elif etype == "done":
                final_state = event.get("state", {})

        try:
            await update.effective_chat.delete_message(status_msg_id)
        except Exception:
            pass

        summary_text = format_telegram_summary(final_state)
        if summary_text:
            await _send(update, summary_text)
        else:
            await _send(update, "✅ <b>Pipeline hoàn thành.</b>")

        report_path = export_report_markdown(final_state)
        if report_path and report_path.exists():
            try:
                with open(report_path, "rb") as f:
                    await update.effective_chat.send_document(
                        document=f,
                        filename=report_path.name,
                        caption="📄 <b>Research Report</b>",
                        parse_mode="HTML",
                    )
            except Exception as e:
                logger.warning("send_document_failed", error=str(e))

        logger.info("pipeline_done", chat_id=update.effective_chat.id)

    except asyncio.CancelledError:
        try:
            await update.effective_chat.delete_message(status_msg_id)
        except Exception:
            pass
        await _send(update, "🛑 <b>Pipeline cancelled.</b>")

    except Exception as exc:
        logger.exception("pipeline_error", error=str(exc))
        try:
            await update.effective_chat.delete_message(status_msg_id)
        except Exception:
            pass
        await _send(update, format_error(exc))

    finally:
        session.active_task = None


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send(
        update,
        "👋 <b>Hệ thống Nghiên cứu Đa Tác nhân</b>\n\n"
        "Gửi cho tôi bất kỳ câu hỏi nghiên cứu nào, tôi sẽ:\n"
        "1️⃣ Làm rõ yêu cầu\n"
        "2️⃣ Lập kế hoạch nghiên cứu\n"
        "3️⃣ Thực thi các tác vụ (tìm kiếm, phân tích, tổng hợp)\n"
        "4️⃣ Tạo báo cáo nghiên cứu\n\n"
        "<b>Lệnh:</b>\n"
        "/cancel — dừng pipeline đang chạy\n"
        "/status — kiểm tra trạng thái pipeline\n"
        "/provider &lt;tên&gt; — đổi nhà cung cấp LLM\n\n"
        "Chỉ cần gõ câu hỏi của bạn để bắt đầu! 🚀",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send(
        update,
        "<b>📖 Hướng dẫn sử dụng</b>\n\n"
        "Gửi bất kỳ câu hỏi nghiên cứu nào. Ví dụ:\n"
        "• <i>Những tiến bộ mới nhất về LLM agents là gì?</i>\n"
        "• <i>So sánh RAG và fine-tuning</i>\n\n"
        "<b>Nhà cung cấp:</b>\n"
        "/provider anthropic — Claude\n"
        "/provider openai — GPT-4o\n"
        "/provider gemini — Gemini (default)\n"
        "/provider ollama — local Ollama\n\n"
        "/cancel — cancel active pipeline\n"
        "/status — check status\n"
        "/delete [N|all] — xóa N tin nhắn gần nhất hoặc tất cả (mặc định 50)",
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data.get("base_config", get_config())
    session = _get_session(update.effective_chat.id, config)
    if session.active_task and not session.active_task.done():
        session.active_task.cancel()
        await _send(update, "🛑 Đang dừng pipeline...")
    else:
        await _send(update, "ℹ️ Không có pipeline nào đang chạy.")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data.get("base_config", get_config())
    session = _get_session(update.effective_chat.id, config)
    if session.active_task and not session.active_task.done():
        await _send(update, "⚙️ <b>Pipeline đang chạy.</b> Dùng /cancel để dừng.")
    else:
        await _send(update, "✅ Không có pipeline nào đang hoạt động. Gửi câu hỏi để bắt đầu.")


async def cmd_provider(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data.get("base_config", get_config())
    session = _get_session(update.effective_chat.id, config)

    args = context.args
    if not args:
        current = session.config.llm_provider.value
        await _send(update, f"Nhà cung cấp hiện tại: <code>{current}</code>\nCách dùng: /provider &lt;anthropic|openai|gemini|ollama|lmstudio&gt;")
        return

    try:
        provider = LLMProvider(args[0].lower())
        session.config = session.config.model_copy(update={"llm_provider": provider})
        await _send(update, f"✅ Đã chuyển sang <code>{args[0]}</code>")
    except ValueError:
        await _send(update, f"❌ Nhà cung cấp không hợp lệ: <code>{args[0]}</code>")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    config = context.bot_data.get("base_config", get_config())
    session = _get_session(update.effective_chat.id, config)

    if session.active_task and not session.active_task.done():
        if session.review_gate.is_waiting:
            session.review_gate.resolve(text)
            return
        await _send(update, "⚠️ Đang có pipeline chạy. Dùng /cancel để dừng trước.")
        return

    logger.info("message_received", chat_id=update.effective_chat.id, text=text[:80])
    await update.effective_chat.send_chat_action(constants.ChatAction.TYPING)

    task = asyncio.create_task(_run_pipeline(update, session, text))
    session.active_task = task


async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg_id = update.message.message_id

    args = context.args
    delete_all = args and args[0].lower() == "all"

    if delete_all:
        count = None
    elif args:
        try:
            count = int(args[0])
        except ValueError:
            await _send(update, "Cách dùng: /delete [N|all] — xóa N tin nhắn gần nhất hoặc tất cả (mặc định: 50)")
            return
    else:
        count = 50

    deleted = 0
    consecutive_errors = 0
    mid = msg_id
    while mid > 0:
        try:
            await chat.delete_message(mid)
            deleted += 1
            consecutive_errors = 0
            if count is not None and deleted >= count:
                break
        except Exception:
            consecutive_errors += 1
            if consecutive_errors > (50 if delete_all else 20):
                break
        mid -= 1

    logger.info("messages_deleted", chat_id=chat.id, deleted=deleted)
    try:
        note = await chat.send_message(f"🗑 Đã xóa {deleted} tin nhắn.", parse_mode="HTML")
        await asyncio.sleep(3)
        await chat.delete_message(note.message_id)
    except Exception:
        pass


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    from telegram.error import Conflict, NetworkError, TimedOut
    err = context.error
    if isinstance(err, Conflict):
        logger.warning("telegram_conflict", hint="Another bot instance is running — stop it first")
    elif isinstance(err, (NetworkError, TimedOut)):
        logger.warning("telegram_network_error", error=str(err))
    else:
        logger.error("telegram_error", error=str(err))


def build_application(token: str, config: AppConfig) -> Application:
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(connect_timeout=10, read_timeout=60, write_timeout=60, media_write_timeout=120)
    app = Application.builder().token(token).request(request).build()
    app.bot_data["base_config"] = config

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("provider", cmd_provider))
    app.add_handler(CommandHandler("delete", cmd_delete))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    return app


async def _set_commands(app: Application) -> None:
    from telegram import BotCommand
    await app.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Show help"),
        BotCommand("cancel", "Cancel active pipeline"),
        BotCommand("status", "Check pipeline status"),
        BotCommand("provider", "Switch LLM provider (anthropic/openai/gemini/ollama)"),
        BotCommand("delete", "Delete last N messages or all (default 50)"),
    ])


def run_bot(token: str, config: Optional[AppConfig] = None) -> None:
    if config is None:
        config = get_config()
    logger.info("bot_starting")
    app = build_application(token, config)
    app.post_init = _set_commands
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

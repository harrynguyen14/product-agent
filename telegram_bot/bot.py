from __future__ import annotations

"""Telegram multi-bot system.

Mỗi role = 1 bot riêng, chạy độc lập bằng token riêng.
Các bot nói chuyện với nhau trong group qua @mention.

Bot types:
  - PM bot  : orchestrator chính. Nhận yêu cầu từ user, mention từng role
               theo thứ tự PM_MANAGES, chờ human gate trước mỗi mention.
  - PD bot  : orchestrator kỹ thuật. Khi bị PM mention, tự mention
               các role trong PD_MANAGES, chờ human gate.
  - Role bot: worker thuần túy (BA, Arch, ...). Khi bị mention → chạy LLM → reply.

Human gate (chỉ PM và PD):
  Trước khi mention role tiếp theo, PM/PD gửi tin hỏi user:
    "[role] sắp làm: <instruction> — gõ ok để tiếp tục"
  User reply ok → tiếp, reply khác → feedback append vào instruction → hỏi lại.

Message routing:
  - PM bot  : lắng nghe mọi text message từ user (không phải bot khác)
  - PD bot  : lắng nghe khi bị @mention
  - Role bot: lắng nghe khi bị @mention
"""

import asyncio
import re
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from telegram import BotCommand, Message, Update, constants
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config.settings import AppConfig, get_config, ROLE_SLUG_TO_NAME
from core.llm_factory import LLMFactory
from infrastructure.logging import get_logger
from roles.registry import RoleRegistry
from telegram_bot.formatters import (
    format_done,
    format_error,
    format_gate_prompt,
    format_role_output,
    format_thinking,
    split_message,
)
from telegram_bot.review_gate import HumanGate
from telegram_bot.session import ChatSession, get_session

logger = get_logger("telegram.bot")


# ---------------------------------------------------------------------------
# Send helpers
# ---------------------------------------------------------------------------

async def _send(chat, text: str, parse_mode: str = "HTML") -> Optional[Message]:
    """Gửi text, tự split nếu quá dài. Trả về Message cuối cùng."""
    from telegram.error import RetryAfter
    last_msg = None
    for chunk in split_message(text):
        for attempt in range(3):
            try:
                last_msg = await chat.send_message(chunk, parse_mode=parse_mode)
                break
            except RetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
            except Exception as exc:
                logger.warning("send_failed", error=str(exc))
                break
    return last_msg


async def _delete(chat, message_id: int) -> None:
    try:
        await chat.delete_message(message_id)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Role executor — dùng chung cho mọi bot
# ---------------------------------------------------------------------------

def _build_registry(config: AppConfig) -> RoleRegistry:
    return RoleRegistry(
        llm=LLMFactory.build(config),
        raw_llm=LLMFactory.build_raw(config),
    )


async def _run_role(
    role_name: str,
    instruction: str,
    context: str,
    registry: RoleRegistry,
) -> str:
    """Chạy 1 role và trả về output string."""
    role = registry.get(role_name)
    if role is None:
        raise ValueError(f"Role không tồn tại: {role_name}")
    return await role.run_task(instruction, upstream_context=context)


# ---------------------------------------------------------------------------
# Gate loop helper — dùng cho PM và PD
# ---------------------------------------------------------------------------

async def _gate_loop(
    chat,
    gate: HumanGate,
    role_slug: str,
    instruction: str,
    config: AppConfig,
) -> str:
    """Hỏi user confirm trước khi chạy role. Trả về instruction cuối cùng (có thể đã chỉnh).

    Arm gate → gửi tin → chờ user reply.
    ok → trả về instruction.
    feedback → append → hỏi lại.
    """
    current = instruction
    while True:
        gate.arm()
        gate_text = format_gate_prompt(
            config.get_role_name(role_slug),
            current,
        )
        await _send(chat, gate_text)

        reply = await gate.wait(timeout=600.0)

        if gate.is_accepted(reply):
            return current
        else:
            current = f"{current}\n\n[Góp ý từ user: {reply}]"
            await _send(
                chat,
                f"📝 Đã nhận góp ý. Cập nhật instruction và hỏi lại...",
            )


# ---------------------------------------------------------------------------
# PM orchestration pipeline
# ---------------------------------------------------------------------------

async def _pm_pipeline(
    update: Update,
    session: ChatSession,
    requirement: str,
    config: AppConfig,
    registry: RoleRegistry,
) -> None:
    """Pipeline chính của PM bot."""
    chat = update.effective_chat
    pm_name = config.get_role_name("pm")
    outputs: dict[str, str] = {"requirement": requirement}

    try:
        status = await _send(chat, "⏳ <b>PM đang phân tích yêu cầu...</b>")
        status_id = status.message_id if status else None

        for role_slug in config.manages():  # ["planner","ba","uiux","pd","reporter"]
            role_name = config.get_role_name(role_slug)
            mention = config.get_mention(role_slug)

            # PM tạo instruction cho role tiếp theo
            pm_role = registry.get(pm_name)
            ctx = _build_context(outputs)
            instruction = await pm_role.run_task(
                f"Yêu cầu dự án: {requirement}\n\nKết quả đã có:\n{ctx}\n\n"
                f"Soạn instruction cụ thể cho {role_name} ({mention}) thực hiện phần việc tiếp theo. "
                "Chỉ trả về nội dung instruction.",
            )

            # Xóa status trước khi hỏi gate
            if status_id:
                await _delete(chat, status_id)
                status_id = None

            # Human gate
            instruction = await _gate_loop(
                chat, session.gate, role_slug, instruction, config
            )

            # Mention role bot trong group
            await _send(
                chat,
                f"{mention} {instruction}",
                parse_mode=None,  # plain text để @mention hoạt động
            )

            # Chờ role bot reply — PD sẽ tự orchestrate team của nó
            # PM chờ reply từ role bot (message từ bot trong group)
            role_output = await _wait_for_role_reply(
                session, role_slug, timeout=1800.0
            )
            outputs[role_slug] = role_output

            status = await _send(chat, "⏳ <b>PM đang xử lý kết quả...</b>")
            status_id = status.message_id if status else None

        if status_id:
            await _delete(chat, status_id)

        await _send(chat, format_done())
        logger.info("pm_pipeline_done", chat_id=chat.id)

    except asyncio.CancelledError:
        await _send(chat, "🛑 <b>Đã dừng pipeline.</b>")
    except Exception as exc:
        logger.exception("pm_pipeline_error", error=str(exc))
        await _send(chat, format_error(exc))
    finally:
        session.active_task = None


# ---------------------------------------------------------------------------
# PD orchestration pipeline (chạy khi PD bị PM mention)
# ---------------------------------------------------------------------------

async def _pd_pipeline(
    chat,
    session: ChatSession,
    instruction: str,
    config: AppConfig,
    registry: RoleRegistry,
) -> str:
    """PD nhận instruction từ PM, tự orchestrate team kỹ thuật, trả về summary."""
    pd_name = config.get_role_name("pd")
    pd_outputs: dict[str, str] = {}

    for role_slug in config.manages():  # ["arch","sec","devops","fe","be","qa"]
        role_name = config.get_role_name(role_slug)
        mention = config.get_mention(role_slug)

        pd_role = registry.get(pd_name)
        ctx = _build_context(pd_outputs)
        sub_instruction = await pd_role.run_task(
            f"Instruction từ PM: {instruction}\n\nKết quả team đã có:\n{ctx}\n\n"
            f"Soạn instruction cụ thể cho {role_name} ({mention}). "
            "Chỉ trả về nội dung instruction.",
        )

        # Human gate
        sub_instruction = await _gate_loop(
            chat, session.gate, role_slug, sub_instruction, config
        )

        # Mention role bot
        await _send(
            chat,
            f"{mention} {sub_instruction}",
            parse_mode=None,
        )

        # Chờ role bot reply
        role_output = await _wait_for_role_reply(
            session, role_slug, timeout=1800.0
        )
        pd_outputs[role_slug] = role_output

    # PD tổng hợp
    pd_role = registry.get(pd_name)
    summary = await pd_role.run_task(
        "Tổng hợp kết quả từ toàn bộ team kỹ thuật:\n\n"
        + "\n\n".join(f"## {k}\n{v}" for k, v in pd_outputs.items()),
    )
    return summary


# ---------------------------------------------------------------------------
# Wait for role reply — simple asyncio event
# ---------------------------------------------------------------------------

async def _wait_for_role_reply(
    session: ChatSession,
    role_slug: str,
    timeout: float = 1800.0,
) -> str:
    """Chờ session.role_reply_gate được resolve với output của role_slug."""
    session.expect_reply_from = role_slug
    session.role_reply_gate.arm()
    try:
        return await session.role_reply_gate.wait(timeout=timeout)
    finally:
        session.expect_reply_from = None


# ---------------------------------------------------------------------------
# Worker role handler (BA, Arch, FE, BE, ...)
# ---------------------------------------------------------------------------

async def _handle_worker_mention(
    chat,
    instruction: str,
    config: AppConfig,
    registry: RoleRegistry,
) -> str:
    """Role bot nhận instruction, chạy LLM, trả về output."""
    role_name = config.get_role_name(config.bot_role)
    status = await _send(chat, format_thinking(role_name))
    status_id = status.message_id if status else None

    output = await _run_role(role_name, instruction, "", registry)

    if status_id:
        await _delete(chat, status_id)

    await _send(chat, format_role_output(role_name, output))
    return output


# ---------------------------------------------------------------------------
# Message handlers
# ---------------------------------------------------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    config: AppConfig = context.bot_data["config"]
    registry: RoleRegistry = context.bot_data["registry"]
    session = get_session(update.effective_chat.id, config)
    chat = update.effective_chat
    bot_role = config.bot_role

    # --- PM bot: nhận yêu cầu từ user thường ---
    if bot_role == "pm":
        # Nếu gate đang chờ → đây là reply gate
        if session.is_busy() and session.gate.is_waiting:
            session.gate.resolve(text)
            return

        if session.is_busy():
            await _send(chat, "⚠️ Pipeline đang chạy. Dùng /cancel để dừng.")
            return

        # Tin nhắn từ bot khác (role reply) → resolve role_reply_gate
        if update.message.from_user and update.message.from_user.is_bot:
            sender_username = update.message.from_user.username or ""
            expected = session.expect_reply_from
            if expected and session.role_reply_gate.is_waiting:
                expected_username = config.get_username(expected).lstrip("@")
                if sender_username.lower() == expected_username.lower():
                    session.role_reply_gate.resolve(text)
            return

        # User thường → bắt đầu pipeline
        logger.info("new_requirement", chat_id=chat.id, text=text[:80])
        await chat.send_chat_action(constants.ChatAction.TYPING)
        task = asyncio.create_task(
            _pm_pipeline(update, session, text, config, registry)
        )
        session.active_task = task

    # --- PD bot: nhận khi bị @mention ---
    elif bot_role == "pd":
        me = context.bot_data.get("me")
        my_username = me.username if me else ""

        # Kiểm tra có bị mention không
        if not _is_mentioned(text, my_username):
            # Nếu gate đang chờ → reply gate
            if session.is_busy() and session.gate.is_waiting:
                session.gate.resolve(text)
            # Role reply từ sub-bot
            elif update.message.from_user and update.message.from_user.is_bot:
                sender_username = (update.message.from_user.username or "").lower()
                expected = session.expect_reply_from
                if expected and session.role_reply_gate.is_waiting:
                    expected_uname = config.get_username(expected).lstrip("@").lower()
                    if sender_username == expected_uname:
                        session.role_reply_gate.resolve(text)
            return

        # Bị mention → lấy instruction (bỏ @mention ra)
        instruction = _strip_mention(text, my_username)
        if not instruction:
            return

        if session.is_busy():
            await _send(chat, "⚠️ PD đang bận. Đợi pipeline hiện tại xong.")
            return

        async def _pd_task():
            try:
                summary = await _pd_pipeline(chat, session, instruction, config, registry)
                # Reply summary vào group để PM nhận
                await _send(chat, format_role_output("ProjectDeveloper", summary))
            except asyncio.CancelledError:
                await _send(chat, "🛑 PD pipeline bị dừng.")
            except Exception as exc:
                logger.exception("pd_pipeline_error", error=str(exc))
                await _send(chat, format_error(exc))
            finally:
                session.active_task = None

        task = asyncio.create_task(_pd_task())
        session.active_task = task

    # --- Worker bot: nhận khi bị @mention ---
    else:
        me = context.bot_data.get("me")
        my_username = me.username if me else ""

        if not _is_mentioned(text, my_username):
            return

        instruction = _strip_mention(text, my_username)
        if not instruction:
            return

        if session.is_busy():
            await _send(chat, "⚠️ Đang xử lý task khác. Đợi chút.")
            return

        async def _worker_task():
            try:
                await _handle_worker_mention(chat, instruction, config, registry)
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.exception("worker_error", error=str(exc))
                await _send(chat, format_error(exc))
            finally:
                session.active_task = None

        task = asyncio.create_task(_worker_task())
        session.active_task = task


# ---------------------------------------------------------------------------
# Mention helpers
# ---------------------------------------------------------------------------

def _is_mentioned(text: str, username: str) -> bool:
    if not username:
        return False
    return bool(re.search(rf"@{re.escape(username)}\b", text, re.IGNORECASE))


def _strip_mention(text: str, username: str) -> str:
    """Bỏ @username ra khỏi text, trim khoảng trắng."""
    cleaned = re.sub(rf"@{re.escape(username)}\b", "", text, flags=re.IGNORECASE)
    return cleaned.strip()


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def _build_context(outputs: dict[str, str]) -> str:
    skip = {"requirement"}
    parts = [
        f"## {k}\n{v}"
        for k, v in outputs.items()
        if k not in skip and v
    ]
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: AppConfig = context.bot_data["config"]
    role_name = config.get_role_name(config.bot_role)
    is_pm = config.bot_role == "pm"
    msg = (
        f"👋 <b>{role_name} Bot</b>\n\n"
        + (
            "Gửi yêu cầu dự án để bắt đầu. Tôi sẽ phối hợp với các role khác.\n\n"
            "<b>Lệnh:</b>\n/cancel — dừng pipeline\n/status — kiểm tra trạng thái"
            if is_pm else
            f"Bot {role_name} sẵn sàng. Mention tôi trong group để giao task.\n\n"
            "<b>Lệnh:</b>\n/cancel — dừng task\n/status — kiểm tra trạng thái"
        )
    )
    await _send(update.effective_chat, msg)


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: AppConfig = context.bot_data["config"]
    session = get_session(update.effective_chat.id, config)
    if session.is_busy():
        session.active_task.cancel()
        await _send(update.effective_chat, "🛑 Đang dừng...")
    else:
        await _send(update.effective_chat, "ℹ️ Không có task nào đang chạy.")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: AppConfig = context.bot_data["config"]
    session = get_session(update.effective_chat.id, config)
    if session.is_busy():
        waiting = session.gate.is_waiting
        state = "⏳ đang chờ xác nhận" if waiting else "⚙️ đang xử lý"
        await _send(update.effective_chat, f"Pipeline {state}. Dùng /cancel để dừng.")
    else:
        await _send(update.effective_chat, "✅ Không có task nào đang chạy.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    from telegram.error import Conflict, NetworkError, TimedOut
    err = context.error
    if isinstance(err, Conflict):
        logger.warning("telegram_conflict")
    elif isinstance(err, (NetworkError, TimedOut)):
        logger.warning("telegram_network_error", error=str(err))
    else:
        logger.error("telegram_error", error=str(err))


# ---------------------------------------------------------------------------
# App builder
# ---------------------------------------------------------------------------

def build_application(config: AppConfig) -> Application:
    from telegram.request import HTTPXRequest

    token = config.get_my_token()
    if not token:
        raise ValueError(
            f"Không tìm thấy token cho role '{config.bot_role}'. "
            f"Set MA_TOKEN_{config.bot_role.upper()} trong .env"
        )

    request = HTTPXRequest(
        connect_timeout=10,
        read_timeout=60,
        write_timeout=60,
        media_write_timeout=120,
    )
    app = Application.builder().token(token).request(request).build()

    registry = _build_registry(config)

    app.bot_data["config"] = config
    app.bot_data["registry"] = registry

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    return app


async def _post_init(app: Application) -> None:
    config: AppConfig = app.bot_data["config"]
    # Lưu bot info để biết username của mình
    me = await app.bot.get_me()
    app.bot_data["me"] = me
    logger.info("bot_ready", username=me.username, role=config.bot_role)

    await app.bot.set_my_commands([
        BotCommand("start", "Giới thiệu bot"),
        BotCommand("cancel", "Dừng task đang chạy"),
        BotCommand("status", "Kiểm tra trạng thái"),
    ])


async def _run_app(app: Application) -> None:
    """Chạy 1 Application (polling) trong async context."""
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )
        # Chạy mãi cho đến khi bị cancel
        await asyncio.Event().wait()


async def run_all_bots(base_config: AppConfig, active_roles: list[str]) -> None:
    """Chạy tất cả role bot song song trong 1 event loop."""
    apps: list[Application] = []
    for role_slug in active_roles:
        role_config = base_config.model_copy(update={"bot_role": role_slug})
        try:
            app = build_application(role_config)
            app.post_init = _post_init
            apps.append(app)
            logger.info("bot_registered", role=role_slug)
        except Exception as exc:
            logger.warning("bot_skipped", role=role_slug, error=str(exc))

    if not apps:
        logger.error("no_bots_started")
        return

    # Khởi động tất cả app, chạy song song
    async with asyncio.TaskGroup() as tg:
        for app in apps:
            tg.create_task(_run_app(app))

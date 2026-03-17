import asyncio
import logging
from dataclasses import dataclass, field

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from telegram_summarizer.config import get_user_limits
from telegram_summarizer.exporter import export_docx, export_pdf
from telegram_summarizer.summarizer import LEVEL_PROMPTS, summarize
from telegram_summarizer.user_manager import NoUsernameError, UserManager

VALID_FORMATS = {"markdown", "pdf", "docx"}
TELEGRAM_MSG_LIMIT = 4096

logger = logging.getLogger(__name__)

BATCH_TIMEOUT_SECONDS = 3


@dataclass
class UserSession:
    messages: list[str] = field(default_factory=list)
    media_file_ids: list[dict] = field(default_factory=list)
    level: str = "mid"
    fmt: str = "markdown"
    save_media: bool = False
    batch_task: asyncio.Task | None = field(default=None, repr=False)


# Per-user sessions keyed by user_id
_sessions: dict[int, UserSession] = {}


def get_session(user_id: int) -> UserSession:
    if user_id not in _sessions:
        _sessions[user_id] = UserSession()
    return _sessions[user_id]


def clear_session(user_id: int) -> None:
    _sessions.pop(user_id, None)


def build_form_keyboard(session: UserSession) -> InlineKeyboardMarkup:
    level_labels = {"min": "Min", "mid": "Mid", "max": "Max"}
    level_buttons = []
    for key, label in level_labels.items():
        text = f"[{label}]" if session.level == key else label
        level_buttons.append(InlineKeyboardButton(text, callback_data=f"level:{key}"))

    fmt_labels = {"markdown": "MD", "pdf": "PDF", "docx": "DOCX"}
    fmt_buttons = []
    for key, label in fmt_labels.items():
        text = f"[{label}]" if session.fmt == key else label
        fmt_buttons.append(InlineKeyboardButton(text, callback_data=f"fmt:{key}"))

    media_text = "[Yes]" if session.save_media else "Yes"
    no_media_text = "[No]" if not session.save_media else "No"
    media_buttons = [
        InlineKeyboardButton(media_text, callback_data="media:yes"),
        InlineKeyboardButton(no_media_text, callback_data="media:no"),
    ]

    confirm_button = [InlineKeyboardButton("Confirm", callback_data="confirm")]

    return InlineKeyboardMarkup(
        [
            level_buttons,
            fmt_buttons,
            media_buttons,
            confirm_button,
        ]
    )


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Forward messages to me and I'll summarize them.\n"
        "Use /process to start summarization after forwarding.\n"
        "Use /stats to see your usage statistics."
    )


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    username = update.effective_user.username
    if not username:
        await update.message.reply_text("You need a Telegram username to use this bot.")
        return

    config = context.bot_data["config"]
    user_manager = UserManager()
    try:
        stats = user_manager.get_stats(username)
    except NoUsernameError:
        await update.message.reply_text("You need a Telegram username to use this bot.")
        return

    limits = get_user_limits(config, username)
    await update.message.reply_text(
        f"Usage stats for @{username}:\n"
        f"Today: {stats['input_tokens_today']}/{limits['input_tokens']} input, "
        f"{stats['output_tokens_today']}/{limits['output_tokens']} output\n"
        f"All time: {stats['input_tokens_total']} input, {stats['output_tokens_total']} output"
    )


async def forwarded_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    username = update.effective_user.username
    if not username:
        await update.message.reply_text("You need a Telegram username to use this bot.")
        return

    user_id = update.effective_user.id
    session = get_session(user_id)

    # Extract text
    text = update.message.text or update.message.caption or ""
    if text:
        session.messages.append(text)

    # Extract media file IDs
    if update.message.photo:
        session.media_file_ids.append(
            {
                "type": "photo",
                "file_id": update.message.photo[-1].file_id,
            }
        )
    elif update.message.document:
        session.media_file_ids.append(
            {
                "type": "document",
                "file_id": update.message.document.file_id,
                "file_name": update.message.document.file_name,
            }
        )

    # Cancel previous batch timer and start new one
    if session.batch_task and not session.batch_task.done():
        session.batch_task.cancel()

    session.batch_task = asyncio.create_task(_show_form_after_timeout(update, context, user_id))


def _build_form_text(session: UserSession) -> str:
    msg_count = len(session.messages)
    media_count = len(session.media_file_ids)
    text = f"Collected {msg_count} message(s)"
    if media_count:
        text += f" with {media_count} media file(s)"
    text += ".\nChoose options and confirm:"
    return text


async def _show_form_after_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    await asyncio.sleep(BATCH_TIMEOUT_SECONDS)
    session = get_session(user_id)
    if not session.messages:
        return

    text = _build_form_text(session)
    keyboard = build_form_keyboard(session)
    await update.message.reply_text(text, reply_markup=keyboard)


async def process_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    username = update.effective_user.username
    if not username:
        await update.message.reply_text("You need a Telegram username to use this bot.")
        return

    user_id = update.effective_user.id
    session = get_session(user_id)

    if not session.messages:
        await update.message.reply_text("No forwarded messages collected. Forward some messages first.")
        return

    # Cancel any pending batch timer
    if session.batch_task and not session.batch_task.done():
        session.batch_task.cancel()

    text = _build_form_text(session)
    keyboard = build_form_keyboard(session)
    await update.message.reply_text(text, reply_markup=keyboard)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    session = get_session(user_id)
    data = query.data

    if data == "confirm":
        await _process_summary(update, context, user_id)
        return

    if data.startswith("level:"):
        value = data.split(":")[1]
        if value in LEVEL_PROMPTS:
            session.level = value
    elif data.startswith("fmt:"):
        value = data.split(":")[1]
        if value in VALID_FORMATS:
            session.fmt = value
    elif data.startswith("media:"):
        session.save_media = data.split(":")[1] == "yes"

    keyboard = build_form_keyboard(session)
    await query.edit_message_reply_markup(reply_markup=keyboard)


async def _process_summary(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    query = update.callback_query
    session = get_session(user_id)
    username = update.effective_user.username
    config = context.bot_data["config"]

    # Send status message
    await query.edit_message_text("Processing your messages...")

    # Check limits with estimated input tokens
    user_manager = UserManager()
    combined_text = "\n\n---\n\n".join(session.messages)
    estimated_input = len(combined_text) // 4
    if not user_manager.check_limits(username, estimated_input, 0, config):
        await query.edit_message_text("Daily token limit exceeded. Try again tomorrow.")
        clear_session(user_id)
        return
    try:
        model = config.get("openai_model", "gpt-4.1-nano")
        result = await summarize(combined_text, session.level, model=model)
    except Exception as e:
        logger.error("Summarization failed: %s", e, exc_info=True)
        await query.edit_message_text("Summarization failed. Please try again later.")
        clear_session(user_id)
        return

    # Check limits with actual usage
    if not user_manager.check_limits(username, result.input_tokens, result.output_tokens, config):
        await query.edit_message_text("Token limit would be exceeded. Try a shorter message or lower level.")
        clear_session(user_id)
        return

    # Record usage
    user_manager.record_usage(username, result.input_tokens, result.output_tokens)

    # Export
    if session.fmt == "markdown":
        text = result.text
        if len(text) > TELEGRAM_MSG_LIMIT:
            await query.edit_message_text(text[:TELEGRAM_MSG_LIMIT])
            for i in range(TELEGRAM_MSG_LIMIT, len(text), TELEGRAM_MSG_LIMIT):
                await query.message.reply_text(text[i : i + TELEGRAM_MSG_LIMIT])
        else:
            await query.edit_message_text(text)
    elif session.fmt == "pdf":
        pdf_bytes = export_pdf(result.text)
        await query.edit_message_text("Here is your summary:")
        await query.message.reply_document(
            document=pdf_bytes,
            filename="summary.pdf",
        )
    elif session.fmt == "docx":
        docx_bytes = export_docx(result.text)
        await query.edit_message_text("Here is your summary:")
        await query.message.reply_document(
            document=docx_bytes,
            filename="summary.docx",
        )

    # Send media if requested (only for pdf/docx)
    if session.save_media and session.fmt != "markdown" and session.media_file_ids:
        for media in session.media_file_ids:
            if media["type"] == "photo":
                await query.message.reply_photo(media["file_id"])
            elif media["type"] == "document":
                await query.message.reply_document(media["file_id"])

    clear_session(user_id)

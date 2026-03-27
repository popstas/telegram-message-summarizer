import asyncio
import logging
from dataclasses import dataclass, field

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from telegram_summarizer.config import get_user_limits
from telegram_summarizer.exporter import export_docx, export_pdf, export_tlg
from telegram_summarizer.summarizer import LEVEL_PROMPTS, STYLE_PROMPTS, summarize
from telegram_summarizer.user_manager import NoUsernameError

VALID_FORMATS = {"markdown", "tlg", "pdf", "docx"}
TELEGRAM_MSG_LIMIT = 4096
TELEGRAM_CAPTION_LIMIT = 1024

logger = logging.getLogger(__name__)

BATCH_TIMEOUT_SECONDS = 3


@dataclass
class UserSession:
    messages: list[str] = field(default_factory=list)
    media_file_ids: list[dict] = field(default_factory=list)
    level: str = "mid"
    fmt: str = "markdown"
    style: str = "instruction"
    save_media: bool = False
    batch_task: asyncio.Task | None = field(default=None, repr=False)


# Per-user sessions keyed by user_id
_sessions: dict[int, UserSession] = {}

# Per-user last processed data for /reprocess
_last_processed: dict[int, dict] = {}


def get_session(user_id: int) -> UserSession:
    if user_id not in _sessions:
        _sessions[user_id] = UserSession()
    return _sessions[user_id]


def clear_session(user_id: int) -> None:
    session = _sessions.pop(user_id, None)
    if session and session.batch_task and not session.batch_task.done():
        session.batch_task.cancel()


async def clear_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    session = _sessions.get(user_id)
    count = len(session.messages) if session else 0
    clear_session(user_id)
    if count:
        await update.message.reply_text(f"Cleared {count} cached message(s).")
    else:
        await update.message.reply_text("No cached messages to clear.")


def build_form_keyboard(session: UserSession) -> InlineKeyboardMarkup:
    level_labels = {"min": "Min", "mid": "Mid", "max": "Max"}
    level_buttons = []
    for key, label in level_labels.items():
        text = f"[{label}]" if session.level == key else label
        level_buttons.append(InlineKeyboardButton(text, callback_data=f"level:{key}"))

    fmt_labels = {"markdown": "MD", "tlg": "TLG", "pdf": "PDF", "docx": "DOCX"}
    fmt_buttons = []
    for key, label in fmt_labels.items():
        text = f"[{label}]" if session.fmt == key else label
        fmt_buttons.append(InlineKeyboardButton(text, callback_data=f"fmt:{key}"))

    style_labels = {"original": "Keep original", "summary": "Summary", "instruction": "Instruction", "blog": "Blog"}
    style_buttons = []
    for key, label in style_labels.items():
        text = f"[{label}]" if session.style == key else label
        style_buttons.append(InlineKeyboardButton(text, callback_data=f"style:{key}"))

    media_text = "[Use media]" if session.save_media else "Use media"
    no_media_text = "[no media]" if not session.save_media else "no media"
    media_buttons = [
        InlineKeyboardButton(media_text, callback_data="media:yes"),
        InlineKeyboardButton(no_media_text, callback_data="media:no"),
    ]

    confirm_button = [InlineKeyboardButton("Confirm", callback_data="confirm")]
    help_button = [InlineKeyboardButton("❓ Help", callback_data="help")]

    return InlineKeyboardMarkup(
        [
            level_buttons,
            fmt_buttons,
            style_buttons,
            media_buttons,
            confirm_button,
            help_button,
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
    user_manager = context.bot_data["user_manager"]
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
    try:
        await asyncio.sleep(BATCH_TIMEOUT_SECONDS)
    except asyncio.CancelledError:
        return
    session = get_session(user_id)
    if not session.messages and not session.media_file_ids:
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

    if not session.messages and not session.media_file_ids:
        await update.message.reply_text("No forwarded messages collected. Forward some messages first.")
        return

    # Cancel any pending batch timer
    if session.batch_task and not session.batch_task.done():
        session.batch_task.cancel()

    text = _build_form_text(session)
    keyboard = build_form_keyboard(session)
    await update.message.reply_text(text, reply_markup=keyboard)


async def reprocess_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    username = update.effective_user.username
    if not username:
        await update.message.reply_text("You need a Telegram username to use this bot.")
        return

    user_id = update.effective_user.id
    if user_id not in _last_processed:
        await update.message.reply_text("No previous messages to reprocess.")
        return

    data = _last_processed[user_id]
    session = get_session(user_id)

    # Cancel any pending batch timer
    if session.batch_task and not session.batch_task.done():
        session.batch_task.cancel()

    session.messages = list(data["messages"])
    session.media_file_ids = [dict(m) for m in data["media_file_ids"]]
    session.level = data["level"]
    session.fmt = data["fmt"]
    session.style = data.get("style", "instruction")
    session.save_media = data["save_media"]

    text = _build_form_text(session)
    keyboard = build_form_keyboard(session)
    await update.message.reply_text(text, reply_markup=keyboard)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    username = update.effective_user.username
    if not username:
        await query.edit_message_text("You need a Telegram username to use this bot.")
        return

    user_id = update.effective_user.id
    session = get_session(user_id)
    data = query.data

    if data == "confirm":
        await _process_summary(update, context, user_id)
        return

    if data == "help":
        await query.message.reply_text(
            "📋 *Processing levels:*\n"
            "• *Min* — close to original, preserves quotes and structure\n"
            "• *Mid* — balanced summary, keeps key points\n"
            "• *Max* — heavily condensed, essential points only\n"
            "\n"
            "✍️ *Styles:*\n"
            "• *Keep original* — preserves author's voice, only cleans up chat artifacts\n"
            "• *Summary* — concise summary of key points\n"
            "• *Instruction* — clear, structured instructional document\n"
            "• *Blog* — engaging blog post with narrative style\n"
            "\n"
            "📄 *Formats:*\n"
            "• *MD* — plain Telegram message\n"
            "• *TLG* — Telegram message with MarkdownV2 formatting and inline media\n"
            "• *PDF* — PDF file\n"
            "• *DOCX* — Word file\n"
            "\n"
            "🖼 *Media:*\n"
            "Attach forwarded photos, videos, and documents to the result "
            "(for TLG/PDF/DOCX formats).",
            parse_mode="Markdown",
        )
        return

    parts = data.split(":", 1)
    if len(parts) != 2:
        return

    prefix, value = parts
    if prefix == "level":
        if value in LEVEL_PROMPTS:
            session.level = value
    elif prefix == "fmt":
        if value in VALID_FORMATS:
            session.fmt = value
    elif prefix == "style":
        if value in STYLE_PROMPTS:
            session.style = value
    elif prefix == "media":
        session.save_media = value == "yes"

    keyboard = build_form_keyboard(session)
    await query.edit_message_reply_markup(reply_markup=keyboard)


async def _process_summary(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    query = update.callback_query
    session = get_session(user_id)
    username = update.effective_user.username
    config = context.bot_data["config"]

    # Send status message
    await query.edit_message_text("Processing your messages...")

    if not session.messages:
        await query.edit_message_text("No text messages to summarize. Only media files were forwarded.")
        clear_session(user_id)
        return

    # Check limits with estimated input tokens
    user_manager = context.bot_data["user_manager"]
    combined_text = "\n\n---\n\n".join(session.messages)
    estimated_input = len(combined_text) // 4
    estimated_output = estimated_input  # conservative estimate for output budget
    if not user_manager.check_limits(username, estimated_input, estimated_output, config):
        await query.edit_message_text("Daily token limit exceeded. Try again tomorrow.")
        clear_session(user_id)
        return
    try:
        model = config.get("openai_model", "gpt-4.1-nano")
        result = await summarize(combined_text, session.level, style=session.style, model=model)
    except Exception as e:
        logger.error("Summarization failed: %s", e, exc_info=True)
        await query.edit_message_text("Summarization failed. Please try again later.")
        clear_session(user_id)
        return

    # Always record usage since tokens were already consumed by the API
    user_manager.record_usage(username, result.input_tokens, result.output_tokens)

    logger.info(
        "Summary completed: user=@%s messages=%d media=%d level=%s style=%s format=%s"
        " save_media=%s input_tokens=%d output_tokens=%d",
        username,
        len(session.messages),
        len(session.media_file_ids),
        session.level,
        session.style,
        session.fmt,
        session.save_media,
        result.input_tokens,
        result.output_tokens,
    )

    # Export and send result
    try:
        if session.fmt == "markdown":
            text = result.text
            if len(text) > TELEGRAM_MSG_LIMIT:
                await query.edit_message_text(text[:TELEGRAM_MSG_LIMIT])
                for i in range(TELEGRAM_MSG_LIMIT, len(text), TELEGRAM_MSG_LIMIT):
                    await query.message.reply_text(text[i : i + TELEGRAM_MSG_LIMIT])
            else:
                await query.edit_message_text(text)
        elif session.fmt == "tlg":
            tlg_text = export_tlg(result.text)
            photos = [m for m in session.media_file_ids if m["type"] == "photo"]
            if session.save_media and photos and len(tlg_text) <= TELEGRAM_CAPTION_LIMIT:
                # Send first photo with caption
                await query.edit_message_text("Here is your summary:")
                await query.message.reply_photo(
                    photos[0]["file_id"],
                    caption=tlg_text,
                    parse_mode="MarkdownV2",
                )
                # Send remaining media separately (skip first photo used as caption)
                first_photo_id = photos[0]["file_id"]
                for media in session.media_file_ids:
                    if media["type"] == "photo" and media["file_id"] == first_photo_id:
                        continue
                    if media["type"] == "photo":
                        await query.message.reply_photo(media["file_id"])
                    elif media["type"] == "document":
                        await query.message.reply_document(media["file_id"])
            else:
                # Send text as message(s), media separately
                if len(tlg_text) > TELEGRAM_MSG_LIMIT:
                    await query.edit_message_text(tlg_text[:TELEGRAM_MSG_LIMIT], parse_mode="MarkdownV2")
                    for i in range(TELEGRAM_MSG_LIMIT, len(tlg_text), TELEGRAM_MSG_LIMIT):
                        await query.message.reply_text(tlg_text[i : i + TELEGRAM_MSG_LIMIT], parse_mode="MarkdownV2")
                else:
                    await query.edit_message_text(tlg_text, parse_mode="MarkdownV2")
                # Send media separately if enabled
                if session.save_media and session.media_file_ids:
                    for media in session.media_file_ids:
                        if media["type"] == "photo":
                            await query.message.reply_photo(media["file_id"])
                        elif media["type"] == "document":
                            await query.message.reply_document(media["file_id"])
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

        # Send media if requested (only for pdf/docx; tlg handles media inline)
        if session.save_media and session.fmt in ("pdf", "docx") and session.media_file_ids:
            for media in session.media_file_ids:
                if media["type"] == "photo":
                    await query.message.reply_photo(media["file_id"])
                elif media["type"] == "document":
                    await query.message.reply_document(media["file_id"])
    except Exception as e:
        logger.error("Export/send failed: %s", e, exc_info=True)
        await query.edit_message_text("Failed to export summary. Please try a different format.")
    finally:
        # Save session data for /reprocess before clearing
        _last_processed[user_id] = {
            "messages": list(session.messages),
            "media_file_ids": [dict(m) for m in session.media_file_ids],
            "level": session.level,
            "fmt": session.fmt,
            "style": session.style,
            "save_media": session.save_media,
        }
        clear_session(user_id)

import logging

from telegram import BotCommand
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from telegram_summarizer.config import load_config
from telegram_summarizer.handlers import (
    callback_handler,
    forwarded_message_handler,
    process_command_handler,
    reprocess_command_handler,
    start_handler,
    stats_handler,
)
from telegram_summarizer.user_manager import UserManager

logger = logging.getLogger(__name__)


def create_application(config: dict | None = None) -> Application:
    if config is None:
        config = load_config()

    builder = Application.builder().token(config["bot_token"])

    proxy_url = config.get("proxy_url", "")
    if proxy_url:
        if "://" not in proxy_url:
            proxy_url = f"http://{proxy_url}"
        builder = builder.proxy(proxy_url).get_updates_proxy(proxy_url)

    app = builder.build()
    app.bot_data["config"] = config
    app.bot_data["user_manager"] = UserManager()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("stats", stats_handler))
    app.add_handler(CommandHandler("process", process_command_handler))
    app.add_handler(CommandHandler("reprocess", reprocess_command_handler))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.FORWARDED & (~filters.COMMAND), forwarded_message_handler))

    app.post_init = _set_bot_commands

    return app


async def _set_bot_commands(application: Application) -> None:
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("process", "Process forwarded messages"),
        BotCommand("reprocess", "Re-summarize last processed messages"),
        BotCommand("stats", "Show usage statistics"),
    ]
    try:
        await application.bot.set_my_commands(commands)
    except Exception:
        logger.warning("Failed to set bot commands menu", exc_info=True)


def run_bot(config: dict | None = None) -> None:
    if config is None:
        config = load_config()
    if not config["bot_token"]:
        logger.error("bot_token not set in data/config.yml")
        return

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    app = create_application(config)
    logger.info("Bot starting...")
    app.run_polling()

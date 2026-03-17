import logging

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
    start_handler,
    stats_handler,
)

logger = logging.getLogger(__name__)


def create_application(config: dict | None = None) -> Application:
    if config is None:
        config = load_config()

    app = Application.builder().token(config["bot_token"]).build()
    app.bot_data["config"] = config

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("stats", stats_handler))
    app.add_handler(CommandHandler("process", process_command_handler))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.FORWARDED & (~filters.COMMAND), forwarded_message_handler))

    return app


def run_bot() -> None:
    config = load_config()
    if not config["bot_token"]:
        logger.error("bot_token not set in data/config.yml")
        return

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    app = create_application(config)
    logger.info("Bot starting...")
    app.run_polling()

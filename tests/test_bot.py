import logging
from unittest.mock import patch

from telegram_summarizer.bot import run_bot


def test_run_bot_suppresses_httpx_logs():
    """Verify httpx logger level is set to WARNING after run_bot configures logging."""
    httpx_logger = logging.getLogger("httpx")
    original_level = httpx_logger.level
    try:
        httpx_logger.setLevel(logging.NOTSET)
        assert httpx_logger.level != logging.WARNING

        config = {"bot_token": "fake-token"}
        with patch("telegram_summarizer.bot.create_application") as mock_create:
            mock_app = mock_create.return_value
            mock_app.run_polling.return_value = None
            run_bot(config)

        assert httpx_logger.level == logging.WARNING
    finally:
        httpx_logger.setLevel(original_level)

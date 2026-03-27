import logging
from unittest.mock import AsyncMock, patch

import pytest
from telegram.ext import CommandHandler

from telegram_summarizer.bot import _set_bot_commands, create_application, run_bot


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


def test_reprocess_command_handler_registered():
    """Verify /reprocess command handler is registered in the application."""
    config = {"bot_token": "fake-token"}
    app = create_application(config)
    command_handlers = [
        h for group_handlers in app.handlers.values() for h in group_handlers if isinstance(h, CommandHandler)
    ]
    commands = {cmd for h in command_handlers for cmd in h.commands}
    assert "reprocess" in commands


def test_post_init_set_to_set_bot_commands():
    """Verify post_init is configured to set bot commands."""
    config = {"bot_token": "fake-token"}
    app = create_application(config)
    assert app.post_init is _set_bot_commands


@pytest.mark.asyncio
async def test_set_bot_commands_calls_api():
    """Verify _set_bot_commands calls bot.set_my_commands with expected commands."""
    mock_app = AsyncMock()
    mock_app.bot.set_my_commands = AsyncMock()

    await _set_bot_commands(mock_app)

    mock_app.bot.set_my_commands.assert_called_once()
    commands = mock_app.bot.set_my_commands.call_args[0][0]
    command_names = [c.command for c in commands]
    assert command_names == ["start", "process", "reprocess", "clear", "stats"]

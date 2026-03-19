"""End-to-end tests using Telethon client to interact with the bot via Telegram API.

These tests require:
- A test bot token configured in data/config.yml (test_bot_token field)
- Telegram API credentials: TELEGRAM_API_ID and TELEGRAM_API_HASH env vars
- A Telethon session file or interactive login on first run

Run with: pytest -m e2e
"""

import asyncio
import os

import pytest
import pytest_asyncio

from telegram_summarizer.config import load_config

# Load config once at module level for skip check
_config = load_config()
_test_bot_token = _config.get("test_bot_token", "")
_api_id = os.environ.get("TELEGRAM_API_ID", "")
_api_hash = os.environ.get("TELEGRAM_API_HASH", "")

_skip_reason = ""
if not _test_bot_token:
    _skip_reason = "test_bot_token not configured in data/config.yml"
elif not _api_id or not _api_hash:
    _skip_reason = "TELEGRAM_API_ID and TELEGRAM_API_HASH env vars required"

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(bool(_skip_reason), reason=_skip_reason),
]


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def running_bot():
    """Start a bot instance using test_bot_token for the duration of e2e tests."""
    from telegram_summarizer.bot import create_application

    config = load_config()
    config["bot_token"] = _test_bot_token
    app = create_application(config)

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    yield app

    await app.updater.stop()
    await app.stop()
    await app.shutdown()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def client(running_bot):
    from telethon import TelegramClient

    session_path = os.environ.get("TELEGRAM_SESSION", "data/e2e_session")
    tg_client = TelegramClient(session_path, int(_api_id), _api_hash)
    await tg_client.start()
    yield tg_client
    await tg_client.disconnect()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def bot_entity(client):
    """Resolve the test bot entity from its token (extract bot username via Bot API)."""
    import json
    import urllib.request

    with urllib.request.urlopen(f"https://api.telegram.org/bot{_test_bot_token}/getMe") as resp:
        data = json.loads(resp.read())
        bot_username = data["result"]["username"]

    entity = await client.get_entity(bot_username)
    return entity


async def _send_and_wait(client, entity, text, wait_seconds=3):
    """Send a message to the bot and wait for a response."""
    await client.send_message(entity, text)
    await asyncio.sleep(wait_seconds)
    messages = await client.get_messages(entity, limit=3)
    # Return bot responses (messages not sent by us)
    bot_messages = [m for m in messages if not m.out]
    return bot_messages


@pytest.mark.e2e
@pytest.mark.asyncio(loop_scope="module")
class TestE2ECommands:
    async def test_start_command(self, client, bot_entity):
        """Test /start returns expected welcome text."""
        responses = await _send_and_wait(client, bot_entity, "/start")
        assert len(responses) > 0
        text = responses[0].text
        assert "Forward messages" in text or "summarize" in text.lower()

    async def test_stats_command(self, client, bot_entity):
        """Test /stats returns usage info."""
        responses = await _send_and_wait(client, bot_entity, "/stats")
        assert len(responses) > 0
        text = responses[0].text
        # Should contain stats or username-related info
        assert "stats" in text.lower() or "usage" in text.lower() or "username" in text.lower()

    async def test_reprocess_without_prior(self, client, bot_entity):
        """Test /reprocess without prior processing returns no-data message."""
        responses = await _send_and_wait(client, bot_entity, "/reprocess")
        assert len(responses) > 0
        text = responses[0].text
        assert "No previous messages" in text or "no previous" in text.lower()

    async def test_forward_and_process_shows_form(self, client, bot_entity):
        """Test forwarding a message then /process shows the options form."""
        # Send a message to Saved Messages (self), then forward it to the bot
        me = await client.get_me()
        sent = await client.send_message(me, "Test message for summarization")
        await client.forward_messages(bot_entity, sent, me)
        await asyncio.sleep(1)
        responses = await _send_and_wait(client, bot_entity, "/process", wait_seconds=4)
        assert len(responses) > 0
        # The form should have inline keyboard buttons or mention "Collected"
        latest = responses[0]
        has_form = (latest.text and "Collected" in latest.text) or latest.buttons is not None
        assert has_form, f"Expected form response, got: {latest.text}"

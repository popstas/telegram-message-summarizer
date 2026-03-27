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

    # Set OpenAI API key from config (normally done in __main__.py)
    if config.get("openai_api_key") and not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = config["openai_api_key"]

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


async def _send_and_wait(client, entity, text, wait_seconds=3, limit=3):
    """Send a message to the bot and wait for a response."""
    await client.send_message(entity, text)
    await asyncio.sleep(wait_seconds)
    messages = await client.get_messages(entity, limit=limit)
    # Return bot responses (messages not sent by us)
    bot_messages = [m for m in messages if not m.out]
    return bot_messages


async def _click_callback(client, bot_entity, msg_id, data):
    """Click an inline button by callback_data."""
    from telethon.tl.functions.messages import GetBotCallbackAnswerRequest

    await client(
        GetBotCallbackAnswerRequest(
            peer=bot_entity,
            msg_id=msg_id,
            data=data.encode() if isinstance(data, str) else data,
        )
    )
    await asyncio.sleep(1)


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
        # Get a bot message to forward (bot messages have forward_origin when forwarded)
        messages = await client.get_messages(bot_entity, limit=5)
        bot_msg = next((m for m in messages if not m.out), None)
        assert bot_msg is not None, "No bot message found to forward"
        await client.forward_messages(bot_entity, bot_msg, bot_entity)
        await asyncio.sleep(1)
        responses = await _send_and_wait(client, bot_entity, "/process", wait_seconds=4)
        assert len(responses) > 0
        latest = responses[0]
        has_form = (latest.text and "Collected" in latest.text) or latest.buttons is not None
        assert has_form, f"Expected form response, got: {latest.text}"

    async def test_reprocess_after_process(self, client, bot_entity):
        """Test /reprocess after a successful process re-shows the form."""
        # Find the form message with "Collected" from the previous test
        messages = await client.get_messages(bot_entity, limit=10)
        form_msg = None
        for m in messages:
            if not m.out and m.text and "Collected" in m.text:
                form_msg = m
                break
        assert form_msg is not None, (
            f"No form message found in: {[(m.id, m.out, m.text[:50] if m.text else None) for m in messages]}"
        )

        # Click Confirm button if buttons are present
        if form_msg.buttons:
            for row in form_msg.buttons:
                for btn in row:
                    if "Confirm" in btn.text:
                        await btn.click()
                        break
        else:
            # Buttons may not be accessible via get_messages; use callback directly
            from telethon.tl.functions.messages import GetBotCallbackAnswerRequest

            await client(
                GetBotCallbackAnswerRequest(
                    peer=bot_entity,
                    msg_id=form_msg.id,
                    data=b"confirm",
                )
            )

        await asyncio.sleep(15)  # wait for OpenAI processing

        # Now test /reprocess
        responses = await _send_and_wait(client, bot_entity, "/reprocess", wait_seconds=5)
        assert len(responses) > 0
        latest = responses[0]
        has_form = (latest.text and "Collected" in latest.text) or latest.buttons is not None
        assert has_form, f"Expected reprocess form, got: {latest.text}"

    async def test_tlg_format_renders_code_blocks(self, client, bot_entity):
        """Test that TLG format correctly renders inline code and code blocks.

        Forwards a message containing code, processes with TLG format + original style,
        and verifies Telegram parsed the MarkdownV2 successfully (code/pre entities present).
        """
        from telethon.tl.types import MessageEntityCode, MessageEntityPre

        # Clear any previous session state
        await _send_and_wait(client, bot_entity, "/clear", wait_seconds=2)

        # Send a message with code, then forward it so the bot collects it
        code_message = (
            "Install:\n"
            "```bash\n"
            "npm i -g happy-coder\n"
            "```\n\n"
            "Run command: `happy codex`"
        )
        sent_msg = await client.send_message(bot_entity, code_message)
        await asyncio.sleep(1)
        await client.forward_messages(bot_entity, sent_msg, bot_entity)
        await asyncio.sleep(2)

        # Start processing — record message ID to filter responses later
        pre_process_msgs = await client.get_messages(bot_entity, limit=1)
        last_id_before = pre_process_msgs[0].id if pre_process_msgs else 0

        responses = await _send_and_wait(client, bot_entity, "/process", wait_seconds=4)
        assert len(responses) > 0
        form_msg = responses[0]
        assert form_msg.text and "Collected" in form_msg.text, (
            f"Expected form, got: {form_msg.text}"
        )

        # Select style:original to preserve code formatting, TLG is default
        await _click_callback(client, bot_entity, form_msg.id, "style:original")
        # Disable media
        await _click_callback(client, bot_entity, form_msg.id, "media:no")
        # Confirm
        await _click_callback(client, bot_entity, form_msg.id, "confirm")

        # Wait for LLM processing
        await asyncio.sleep(20)

        # Get bot response messages sent AFTER we started processing
        messages = await client.get_messages(bot_entity, limit=15)
        bot_responses = [
            m
            for m in messages
            if not m.out
            and m.id > last_id_before
            and m.text
            and "Collected" not in m.text
            and "Cleared" not in m.text
        ]
        assert len(bot_responses) > 0, (
            f"No summary response received. "
            f"All messages: {[(m.id, m.out, m.text[:60] if m.text else None) for m in messages]}"
        )

        # The summary response should have been sent with parse_mode=MarkdownV2.
        # If MarkdownV2 parsing succeeded, Telegram creates entities for code/pre.
        # Check that at least one response has code or pre entities.
        has_code_entity = False
        for msg in bot_responses:
            if msg.entities:
                for entity in msg.entities:
                    if isinstance(entity, (MessageEntityCode, MessageEntityPre)):
                        has_code_entity = True
                        break
            if has_code_entity:
                break

        assert has_code_entity, (
            f"Expected code/pre entities in TLG response, but none found. "
            f"Response texts: {[m.text[:200] for m in bot_responses]}"
        )

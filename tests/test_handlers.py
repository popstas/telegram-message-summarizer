from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from telegram_summarizer.handlers import (
    UserSession,
    _last_processed,
    _sessions,
    build_form_keyboard,
    callback_handler,
    clear_session,
    forwarded_message_handler,
    get_session,
    process_command_handler,
    reprocess_command_handler,
    start_handler,
    stats_handler,
)


@pytest.fixture(autouse=True)
def clear_all_sessions():
    _sessions.clear()
    _last_processed.clear()
    yield
    _sessions.clear()
    _last_processed.clear()


def make_update(user_id=123, username="testuser", text="hello", is_forwarded=True):
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.username = username
    update.message.text = text
    update.message.caption = None
    update.message.photo = []
    update.message.document = None
    update.message.reply_text = AsyncMock()
    if is_forwarded:
        update.message.forward_date = True
    else:
        update.message.forward_date = None
    return update


def make_context(config=None, user_manager=None):
    context = MagicMock()
    context.bot_data = {
        "config": config
        or {
            "bot_token": "test",
            "openai_api_key": "test",
            "openai_model": "gpt-4.1-nano",
            "default_limits": {"input_tokens": 10000, "output_tokens": 10000},
            "users": {},
        },
        "user_manager": user_manager or MagicMock(),
    }
    return context


class TestUserSession:
    def test_get_session_creates_new(self):
        session = get_session(1)
        assert session.messages == []
        assert session.level == "mid"
        assert session.fmt == "markdown"
        assert session.save_media is False

    def test_get_session_returns_existing(self):
        session1 = get_session(1)
        session1.messages.append("test")
        session2 = get_session(1)
        assert session2.messages == ["test"]

    def test_clear_session(self):
        get_session(1).messages.append("test")
        clear_session(1)
        session = get_session(1)
        assert session.messages == []

    def test_clear_nonexistent_session(self):
        clear_session(999)  # Should not raise


class TestBuildFormKeyboard:
    def test_default_selections(self):
        session = UserSession()
        keyboard = build_form_keyboard(session)
        rows = keyboard.inline_keyboard

        assert len(rows) == 5  # level, format, media, confirm, help

        # Level row - mid selected
        level_texts = [b.text for b in rows[0]]
        assert level_texts == ["Min", "[Mid]", "Max"]

        # Format row - markdown selected
        fmt_texts = [b.text for b in rows[1]]
        assert fmt_texts == ["[MD]", "PDF", "DOCX"]

        # Media row - no selected
        media_texts = [b.text for b in rows[2]]
        assert media_texts == ["Use media", "[no media]"]

        # Confirm
        assert rows[3][0].text == "Confirm"

    def test_custom_selections(self):
        session = UserSession(level="max", fmt="pdf", save_media=True)
        keyboard = build_form_keyboard(session)
        rows = keyboard.inline_keyboard

        level_texts = [b.text for b in rows[0]]
        assert level_texts == ["Min", "Mid", "[Max]"]

        fmt_texts = [b.text for b in rows[1]]
        assert fmt_texts == ["MD", "[PDF]", "DOCX"]

        media_texts = [b.text for b in rows[2]]
        assert media_texts == ["[Use media]", "no media"]

    def test_callback_data(self):
        session = UserSession()
        keyboard = build_form_keyboard(session)
        rows = keyboard.inline_keyboard

        assert rows[0][0].callback_data == "level:min"
        assert rows[0][1].callback_data == "level:mid"
        assert rows[0][2].callback_data == "level:max"
        assert rows[1][0].callback_data == "fmt:markdown"
        assert rows[1][1].callback_data == "fmt:pdf"
        assert rows[1][2].callback_data == "fmt:docx"
        assert rows[2][0].callback_data == "media:yes"
        assert rows[2][1].callback_data == "media:no"
        assert rows[3][0].callback_data == "confirm"


class TestStartHandler:
    @pytest.mark.asyncio
    async def test_start(self):
        update = make_update()
        context = make_context()
        await start_handler(update, context)
        update.message.reply_text.assert_called_once()
        call_text = update.message.reply_text.call_args[0][0]
        assert "Forward messages" in call_text


class TestStatsHandler:
    @pytest.mark.asyncio
    async def test_no_username(self):
        update = make_update(username=None)
        context = make_context()
        await stats_handler(update, context)
        call_text = update.message.reply_text.call_args[0][0]
        assert "username" in call_text.lower()

    @pytest.mark.asyncio
    async def test_with_username(self):
        update = make_update(username="testuser")
        mock_um = MagicMock()
        mock_um.get_stats.return_value = {
            "username": "testuser",
            "input_tokens_today": 100,
            "output_tokens_today": 50,
            "input_tokens_total": 500,
            "output_tokens_total": 250,
            "last_reset_date": "2026-03-17",
        }
        context = make_context(user_manager=mock_um)
        await stats_handler(update, context)
        call_text = update.message.reply_text.call_args[0][0]
        assert "100" in call_text
        assert "50" in call_text


class TestForwardedMessageHandler:
    @pytest.mark.asyncio
    async def test_collects_text(self):
        update = make_update(text="Hello world")
        context = make_context()
        with patch("telegram_summarizer.handlers._show_form_after_timeout", new_callable=AsyncMock):
            await forwarded_message_handler(update, context)
        session = get_session(123)
        assert session.messages == ["Hello world"]

    @pytest.mark.asyncio
    async def test_collects_multiple_messages(self):
        context = make_context()
        with patch("telegram_summarizer.handlers._show_form_after_timeout", new_callable=AsyncMock):
            update1 = make_update(text="First")
            await forwarded_message_handler(update1, context)
            update2 = make_update(text="Second")
            await forwarded_message_handler(update2, context)
        session = get_session(123)
        assert session.messages == ["First", "Second"]

    @pytest.mark.asyncio
    async def test_no_username_rejected(self):
        update = make_update(username=None)
        context = make_context()
        await forwarded_message_handler(update, context)
        call_text = update.message.reply_text.call_args[0][0]
        assert "username" in call_text.lower()

    @pytest.mark.asyncio
    async def test_collects_photo(self):
        update = make_update(text="")
        mock_photo = MagicMock()
        mock_photo.file_id = "photo123"
        update.message.text = ""
        update.message.photo = [MagicMock(), mock_photo]  # Last is largest
        context = make_context()
        with patch("telegram_summarizer.handlers._show_form_after_timeout", new_callable=AsyncMock):
            await forwarded_message_handler(update, context)
        session = get_session(123)
        assert len(session.media_file_ids) == 1
        assert session.media_file_ids[0]["type"] == "photo"
        assert session.media_file_ids[0]["file_id"] == "photo123"

    @pytest.mark.asyncio
    async def test_collects_document(self):
        update = make_update(text="")
        update.message.text = ""
        update.message.photo = []
        mock_doc = MagicMock()
        mock_doc.file_id = "doc123"
        mock_doc.file_name = "test.txt"
        update.message.document = mock_doc
        context = make_context()
        with patch("telegram_summarizer.handlers._show_form_after_timeout", new_callable=AsyncMock):
            await forwarded_message_handler(update, context)
        session = get_session(123)
        assert len(session.media_file_ids) == 1
        assert session.media_file_ids[0]["type"] == "document"


class TestProcessCommandHandler:
    @pytest.mark.asyncio
    async def test_no_messages(self):
        update = make_update()
        context = make_context()
        await process_command_handler(update, context)
        call_text = update.message.reply_text.call_args[0][0]
        assert "No forwarded" in call_text

    @pytest.mark.asyncio
    async def test_shows_form(self):
        session = get_session(123)
        session.messages = ["msg1", "msg2"]
        update = make_update()
        context = make_context()
        await process_command_handler(update, context)
        call_text = update.message.reply_text.call_args[0][0]
        assert "2 message" in call_text
        assert update.message.reply_text.call_args[1]["reply_markup"] is not None

    @pytest.mark.asyncio
    async def test_no_username(self):
        update = make_update(username=None)
        context = make_context()
        await process_command_handler(update, context)
        call_text = update.message.reply_text.call_args[0][0]
        assert "username" in call_text.lower()


class TestCallbackHandler:
    def _make_callback_update(self, data, user_id=123, username="testuser"):
        update = MagicMock()
        update.effective_user.id = user_id
        update.effective_user.username = username
        update.callback_query.data = data
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_reply_markup = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.callback_query.message.reply_text = AsyncMock()
        update.callback_query.message.reply_document = AsyncMock()
        update.callback_query.message.reply_photo = AsyncMock()
        return update

    @pytest.mark.asyncio
    async def test_level_change(self):
        get_session(123)
        update = self._make_callback_update("level:max")
        context = make_context()
        await callback_handler(update, context)
        session = get_session(123)
        assert session.level == "max"
        update.callback_query.edit_message_reply_markup.assert_called_once()

    @pytest.mark.asyncio
    async def test_format_change(self):
        get_session(123)
        update = self._make_callback_update("fmt:pdf")
        context = make_context()
        await callback_handler(update, context)
        session = get_session(123)
        assert session.fmt == "pdf"

    @pytest.mark.asyncio
    async def test_media_toggle(self):
        get_session(123)
        update = self._make_callback_update("media:yes")
        context = make_context()
        await callback_handler(update, context)
        session = get_session(123)
        assert session.save_media is True

    @pytest.mark.asyncio
    async def test_confirm_calls_summarizer(self):
        session = get_session(123)
        session.messages = ["test message"]

        update = self._make_callback_update("confirm")
        mock_um = MagicMock()
        mock_um.check_limits.return_value = True
        context = make_context(user_manager=mock_um)

        mock_result = MagicMock()
        mock_result.text = "Summary text"
        mock_result.input_tokens = 10
        mock_result.output_tokens = 5

        with patch("telegram_summarizer.handlers.summarize", new_callable=AsyncMock, return_value=mock_result):
            await callback_handler(update, context)

        # Status message edited with result
        edit_calls = update.callback_query.edit_message_text.call_args_list
        assert any("Summary text" in str(call) for call in edit_calls)

    @pytest.mark.asyncio
    async def test_confirm_pdf_sends_file(self):
        session = get_session(123)
        session.messages = ["test message"]
        session.fmt = "pdf"

        update = self._make_callback_update("confirm")
        mock_um = MagicMock()
        mock_um.check_limits.return_value = True
        context = make_context(user_manager=mock_um)

        mock_result = MagicMock()
        mock_result.text = "Summary text"
        mock_result.input_tokens = 10
        mock_result.output_tokens = 5

        with patch("telegram_summarizer.handlers.summarize", new_callable=AsyncMock, return_value=mock_result):
            await callback_handler(update, context)

        update.callback_query.message.reply_document.assert_called_once()
        call_kwargs = update.callback_query.message.reply_document.call_args[1]
        assert call_kwargs["filename"] == "summary.pdf"

    @pytest.mark.asyncio
    async def test_confirm_docx_sends_file(self):
        session = get_session(123)
        session.messages = ["test message"]
        session.fmt = "docx"

        update = self._make_callback_update("confirm")
        mock_um = MagicMock()
        mock_um.check_limits.return_value = True
        context = make_context(user_manager=mock_um)

        mock_result = MagicMock()
        mock_result.text = "Summary text"
        mock_result.input_tokens = 10
        mock_result.output_tokens = 5

        with patch("telegram_summarizer.handlers.summarize", new_callable=AsyncMock, return_value=mock_result):
            await callback_handler(update, context)

        update.callback_query.message.reply_document.assert_called_once()
        call_kwargs = update.callback_query.message.reply_document.call_args[1]
        assert call_kwargs["filename"] == "summary.docx"

    @pytest.mark.asyncio
    async def test_confirm_summarize_error(self):
        session = get_session(123)
        session.messages = ["test message"]

        update = self._make_callback_update("confirm")
        mock_um = MagicMock()
        mock_um.check_limits.return_value = True
        context = make_context(user_manager=mock_um)

        with patch(
            "telegram_summarizer.handlers.summarize",
            new_callable=AsyncMock,
            side_effect=RuntimeError("API connection failed"),
        ):
            await callback_handler(update, context)

        calls = update.callback_query.edit_message_text.call_args_list
        last_text = calls[-1][0][0]
        assert "failed" in last_text.lower()
        # Should NOT expose internal error details
        assert "API connection failed" not in last_text
        # Session should be cleared
        new_session = get_session(123)
        assert new_session.messages == []

    @pytest.mark.asyncio
    async def test_confirm_always_records_usage(self):
        session = get_session(123)
        session.messages = ["test message"]

        update = self._make_callback_update("confirm")
        mock_um = MagicMock()
        mock_um.check_limits.return_value = True
        context = make_context(user_manager=mock_um)

        mock_result = MagicMock()
        mock_result.text = "Summary text"
        mock_result.input_tokens = 50000
        mock_result.output_tokens = 50000

        with patch("telegram_summarizer.handlers.summarize", new_callable=AsyncMock, return_value=mock_result):
            await callback_handler(update, context)

        # Usage is always recorded since API tokens were already consumed
        mock_um.record_usage.assert_called_once_with("testuser", 50000, 50000)

    @pytest.mark.asyncio
    async def test_callback_invalid_level_ignored(self):
        get_session(123)
        update = self._make_callback_update("level:invalid")
        context = make_context()
        await callback_handler(update, context)
        session = get_session(123)
        assert session.level == "mid"  # Default unchanged

    @pytest.mark.asyncio
    async def test_callback_invalid_format_ignored(self):
        get_session(123)
        update = self._make_callback_update("fmt:invalid")
        context = make_context()
        await callback_handler(update, context)
        session = get_session(123)
        assert session.fmt == "markdown"  # Default unchanged

    @pytest.mark.asyncio
    async def test_confirm_limit_exceeded(self):
        session = get_session(123)
        session.messages = ["test message"]

        update = self._make_callback_update("confirm")
        mock_um = MagicMock()
        mock_um.check_limits.return_value = False
        context = make_context(user_manager=mock_um)

        await callback_handler(update, context)

        # Last call should contain the limit message
        calls = update.callback_query.edit_message_text.call_args_list
        last_text = calls[-1][0][0]
        assert "limit" in last_text.lower()

    @pytest.mark.asyncio
    async def test_confirm_with_media_pdf(self):
        session = get_session(123)
        session.messages = ["test message"]
        session.fmt = "pdf"
        session.save_media = True
        session.media_file_ids = [
            {"type": "photo", "file_id": "photo123"},
            {"type": "document", "file_id": "doc456", "file_name": "test.txt"},
        ]

        update = self._make_callback_update("confirm")
        mock_um = MagicMock()
        mock_um.check_limits.return_value = True
        context = make_context(user_manager=mock_um)

        mock_result = MagicMock()
        mock_result.text = "Summary text"
        mock_result.input_tokens = 10
        mock_result.output_tokens = 5

        with patch("telegram_summarizer.handlers.summarize", new_callable=AsyncMock, return_value=mock_result):
            await callback_handler(update, context)

        update.callback_query.message.reply_photo.assert_called_once_with("photo123")
        update.callback_query.message.reply_document.assert_any_call("doc456")

    @pytest.mark.asyncio
    async def test_confirm_media_ignored_for_markdown(self):
        session = get_session(123)
        session.messages = ["test message"]
        session.fmt = "markdown"
        session.save_media = True
        session.media_file_ids = [{"type": "photo", "file_id": "photo123"}]

        update = self._make_callback_update("confirm")
        mock_um = MagicMock()
        mock_um.check_limits.return_value = True
        context = make_context(user_manager=mock_um)

        mock_result = MagicMock()
        mock_result.text = "Summary text"
        mock_result.input_tokens = 10
        mock_result.output_tokens = 5

        with patch("telegram_summarizer.handlers.summarize", new_callable=AsyncMock, return_value=mock_result):
            await callback_handler(update, context)

        # Photo should NOT be sent for markdown
        update.callback_query.message.reply_photo.assert_not_called()

    @pytest.mark.asyncio
    async def test_confirm_records_usage(self):
        session = get_session(123)
        session.messages = ["test message"]

        update = self._make_callback_update("confirm")
        mock_um = MagicMock()
        mock_um.check_limits.return_value = True
        context = make_context(user_manager=mock_um)

        mock_result = MagicMock()
        mock_result.text = "Summary text"
        mock_result.input_tokens = 100
        mock_result.output_tokens = 50

        with patch("telegram_summarizer.handlers.summarize", new_callable=AsyncMock, return_value=mock_result):
            await callback_handler(update, context)

        mock_um.record_usage.assert_called_once_with("testuser", 100, 50)

    @pytest.mark.asyncio
    async def test_confirm_logs_summary_line(self, caplog):
        session = get_session(123)
        session.messages = ["msg1", "msg2", "msg3"]
        session.media_file_ids = [{"type": "photo", "file_id": "p1"}]
        session.level = "max"
        session.fmt = "pdf"
        session.save_media = True

        update = self._make_callback_update("confirm")
        mock_um = MagicMock()
        mock_um.check_limits.return_value = True
        context = make_context(user_manager=mock_um)

        mock_result = MagicMock()
        mock_result.text = "Summary text"
        mock_result.input_tokens = 1234
        mock_result.output_tokens = 567

        with patch("telegram_summarizer.handlers.summarize", new_callable=AsyncMock, return_value=mock_result):
            import logging

            with caplog.at_level(logging.INFO, logger="telegram_summarizer.handlers"):
                await callback_handler(update, context)

        log_line = [r for r in caplog.records if "Summary completed" in r.message]
        assert len(log_line) == 1
        msg = log_line[0].message
        assert "user=@testuser" in msg
        assert "messages=3" in msg
        assert "media=1" in msg
        assert "level=max" in msg
        assert "format=pdf" in msg
        assert "save_media=True" in msg
        assert "input_tokens=1234" in msg
        assert "output_tokens=567" in msg

    @pytest.mark.asyncio
    async def test_confirm_no_summary_log_on_error(self, caplog):
        session = get_session(123)
        session.messages = ["msg1"]
        session.level = "min"
        session.fmt = "markdown"
        session.save_media = False

        update = self._make_callback_update("confirm")
        mock_um = MagicMock()
        mock_um.check_limits.return_value = True
        context = make_context(user_manager=mock_um)

        with patch(
            "telegram_summarizer.handlers.summarize",
            new_callable=AsyncMock,
            side_effect=Exception("API error"),
        ):
            import logging

            with caplog.at_level(logging.INFO, logger="telegram_summarizer.handlers"):
                await callback_handler(update, context)

        log_line = [r for r in caplog.records if "Summary completed" in r.message]
        assert len(log_line) == 0

    @pytest.mark.asyncio
    async def test_session_cleared_after_confirm(self):
        session = get_session(123)
        session.messages = ["test message"]

        update = self._make_callback_update("confirm")
        mock_um = MagicMock()
        mock_um.check_limits.return_value = True
        context = make_context(user_manager=mock_um)

        mock_result = MagicMock()
        mock_result.text = "Summary text"
        mock_result.input_tokens = 10
        mock_result.output_tokens = 5

        with patch("telegram_summarizer.handlers.summarize", new_callable=AsyncMock, return_value=mock_result):
            await callback_handler(update, context)

        # Session should be cleared
        new_session = get_session(123)
        assert new_session.messages == []


class TestReprocessCommandHandler:
    @pytest.mark.asyncio
    async def test_no_previous_data(self):
        update = make_update()
        context = make_context()
        await reprocess_command_handler(update, context)
        call_text = update.message.reply_text.call_args[0][0]
        assert "No previous messages" in call_text

    @pytest.mark.asyncio
    async def test_no_username(self):
        update = make_update(username=None)
        context = make_context()
        await reprocess_command_handler(update, context)
        call_text = update.message.reply_text.call_args[0][0]
        assert "username" in call_text.lower()

    @pytest.mark.asyncio
    async def test_restores_session_and_shows_form(self):
        _last_processed[123] = {
            "messages": ["msg1", "msg2"],
            "media_file_ids": [{"type": "photo", "file_id": "p1"}],
            "level": "max",
            "fmt": "pdf",
            "save_media": True,
        }
        update = make_update()
        context = make_context()
        await reprocess_command_handler(update, context)

        call_text = update.message.reply_text.call_args[0][0]
        assert "2 message" in call_text
        assert update.message.reply_text.call_args[1]["reply_markup"] is not None

        session = get_session(123)
        assert session.messages == ["msg1", "msg2"]
        assert session.level == "max"
        assert session.fmt == "pdf"
        assert session.save_media is True
        assert len(session.media_file_ids) == 1

    @pytest.mark.asyncio
    async def test_last_processed_saved_after_confirm(self):
        session = get_session(123)
        session.messages = ["test message"]
        session.level = "min"
        session.fmt = "docx"
        session.save_media = True
        session.media_file_ids = [{"type": "photo", "file_id": "p1"}]

        update = MagicMock()
        update.effective_user.id = 123
        update.effective_user.username = "testuser"
        update.callback_query.data = "confirm"
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_reply_markup = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.callback_query.message.reply_text = AsyncMock()
        update.callback_query.message.reply_document = AsyncMock()
        update.callback_query.message.reply_photo = AsyncMock()

        mock_um = MagicMock()
        mock_um.check_limits.return_value = True
        context = make_context(user_manager=mock_um)

        mock_result = MagicMock()
        mock_result.text = "Summary"
        mock_result.input_tokens = 10
        mock_result.output_tokens = 5

        with patch("telegram_summarizer.handlers.summarize", new_callable=AsyncMock, return_value=mock_result):
            await callback_handler(update, context)

        assert 123 in _last_processed
        assert _last_processed[123]["messages"] == ["test message"]
        assert _last_processed[123]["level"] == "min"
        assert _last_processed[123]["fmt"] == "docx"
        assert _last_processed[123]["save_media"] is True

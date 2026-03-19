# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Telegram bot for summarizing forwarded messages. Users forward a batch of messages, choose processing level (min/mid/max), summarization style (original/instruction/blog), output format (markdown/pdf/docx), and whether to save media. The bot summarizes via OpenAI API and returns the result with optional file attachments.

## Tech Stack

- **Language**: Python (use `.venv` for virtual environment)
- **Bot framework**: python-telegram-bot
- **LLM**: OpenAI API via official OpenAI Agents SDK (openai-agents)
- **Config**: YAML (pyyaml)
- **Storage**: SQLite for user limits/statistics (`data/users.db`)
- **Export**: fpdf2 for PDF, python-docx for DOCX
- **E2E testing**: Telethon (Telegram client for end-to-end tests)
- **Deployment**: Docker Compose

## Commands

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run
python -m telegram_summarizer

# Tests
pytest
pytest tests/test_module.py::test_function  # single test
bash data/e2e-test.sh # run e2e tests with filled tokens

# Code quality
ruff check .
ruff format --check .

# Docker
docker-compose up
```

## Architecture

- **Bot handler**: receives forwarded messages, presents interactive form (processing level, style, format, media toggle)
- **Message processor**: collects forwarded messages into context
- **Summarizer**: calls OpenAI API with agent SDK, applies processing level and style (LEVEL_PROMPTS + STYLE_PROMPTS combined)
- **Exporter**: converts summary to markdown/pdf/docx, attaches media
- **User manager**: username-based auth, per-user token limits (input/output), daily and all-time statistics
- **Config**: YAML file with default limits (10k input, 10k output tokens) and per-username overrides
- **Reprocess**: stores last processed session per user (`_last_processed` dict in handlers.py), /reprocess restores and re-shows the form
- **Bot commands menu**: registered via `post_init` callback using `bot.set_my_commands` (start, process, reprocess, stats)

## Key Design Decisions

- Only users with a Telegram username can use the bot
- Status message is sent immediately, then edited in-place as processing completes
- Token usage tracked per user (input + output separately)
- User limits configurable per-username in config, with defaults

## E2E Tests

End-to-end tests use Telethon to interact with a test bot via Telegram API. They require:
- `test_bot_token` in `data/config.yml`
- `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` environment variables
- E2e tests are excluded by default; run with `pytest -m e2e`

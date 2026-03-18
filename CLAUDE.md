# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Telegram bot for summarizing forwarded messages. Users forward a batch of messages, choose processing level (min/mid/max), output format (markdown/pdf/docx), and whether to save media. The bot summarizes via OpenAI API and returns the result with optional file attachments.

## Tech Stack

- **Language**: Python (use `.venv` for virtual environment)
- **Bot framework**: python-telegram-bot
- **LLM**: OpenAI API via official OpenAI Agents SDK (openai-agents)
- **Config**: YAML (pyyaml)
- **Storage**: SQLite for user limits/statistics (`data/users.db`)
- **Export**: fpdf2 for PDF, python-docx for DOCX
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

# Code quality
ruff check .
ruff format --check .

# Docker
docker-compose up
```

## Architecture

- **Bot handler**: receives forwarded messages, presents interactive form (processing level, format, media toggle)
- **Message processor**: collects forwarded messages into context
- **Summarizer**: calls OpenAI API with agent SDK, applies processing level
- **Exporter**: converts summary to markdown/pdf/docx, attaches media
- **User manager**: username-based auth, per-user token limits (input/output), daily and all-time statistics
- **Config**: YAML file with default limits (10k input, 10k output tokens) and per-username overrides

## Key Design Decisions

- Only users with a Telegram username can use the bot
- Status message is sent immediately, then edited in-place as processing completes
- Token usage tracked per user (input + output separately)
- User limits configurable per-username in config, with defaults

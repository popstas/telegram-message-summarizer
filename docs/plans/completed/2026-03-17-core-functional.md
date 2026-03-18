# Core Functional Implementation

## Overview

Implement the complete Telegram message summarizer bot from scratch. The bot receives forwarded messages, presents an interactive form (processing level, format, media toggle), summarizes via OpenAI API, and returns results in the chosen format. Includes user auth, token tracking, and limits.

## Context

- Files involved: all new (greenfield project)
- Related patterns: CLAUDE.md defines architecture, tech stack, and commands
- Dependencies: python-telegram-bot or aiogram, openai (agents SDK, openai-agents), python-docx, reportlab or fpdf2, pyyaml, ruff, pytest
- Data directory: all user-created/changed files (config, database) live in `data/`

## Development Approach

- **Testing approach**: Regular (code first, then tests)
- Complete each task fully before moving to the next
- Use .venv for Python virtual environment
- **CRITICAL: every task MUST include new/updated tests**
- **CRITICAL: all tests must pass before starting next task**

## Implementation Steps

### Task 1: Project scaffolding and configuration

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `data/config.example.yml` (example config, copied to `data/config.yml` by user)
- Create: `telegram_summarizer/__init__.py`
- Create: `telegram_summarizer/__main__.py`
- Create: `telegram_summarizer/config.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `.gitignore` entry for `data/config.yml` and `data/*.db`

- [x] Initialize pyproject.toml with project metadata, ruff config, pytest config
- [x] Create requirements.txt with all dependencies
- [x] Create config.py that loads YAML config from `data/config.yml` with defaults (bot token, OpenAI key, default limits 10k/10k, per-username overrides)
- [x] Create `data/config.example.yml` showing all options
- [x] Create __main__.py entry point (just imports and starts bot)
- [x] Ensure `data/` directory exists (create if missing at startup)
- [x] Add `data/config.yml` and `data/*.db` to .gitignore
- [x] Set up .venv, install deps
- [x] Write tests for config loading (default values, per-user overrides, missing file handling)
- [x] Run pytest - must pass before task 2

### Task 2: User manager with token tracking and limits

**Files:**
- Create: `telegram_summarizer/user_manager.py`
- Create: `tests/test_user_manager.py`

- [x] Implement UserManager class using SQLite storage at `data/users.db`
- [x] Store per-user: username, input_tokens_today, output_tokens_today, input_tokens_total, output_tokens_total, last_reset_date
- [x] Implement daily reset logic (reset counters when date changes)
- [x] Implement check_limits(username, input_tokens, output_tokens) - returns bool
- [x] Implement record_usage(username, input_tokens, output_tokens)
- [x] Implement get_stats(username) - returns usage dict
- [x] Reject users without username
- [x] Write tests: limit checking, usage recording, daily reset, no-username rejection
- [x] Run pytest - must pass before task 3

### Task 3: Summarizer with OpenAI Agents SDK

**Files:**
- Create: `telegram_summarizer/summarizer.py`
- Create: `tests/test_summarizer.py`

- [x] Implement summarize(messages_text, level) using OpenAI Agents SDK
- [x] Define three processing levels: min (mostly quotes, minimal rewrite), mid (balanced summary), max (heavy condensation)
- [x] Build appropriate system prompts for each level
- [x] Return summary text and token usage (input + output counts)
- [x] Write tests with mocked OpenAI calls: verify correct prompts per level, token counting
- [x] Run pytest - must pass before task 4

### Task 4: Exporter (markdown, PDF, DOCX)

**Files:**
- Create: `telegram_summarizer/exporter.py`
- Create: `tests/test_exporter.py`

- [x] Implement export_markdown(summary_text) - returns text as-is
- [x] Implement export_pdf(summary_text) - generate PDF using fpdf2 or reportlab, return bytes
- [x] Implement export_docx(summary_text) - generate DOCX using python-docx, return bytes
- [x] Write tests: each format produces valid output, handles unicode/long text
- [x] Run pytest - must pass before task 5

### Task 5: Telegram bot handler with interactive form

**Files:**
- Create: `telegram_summarizer/bot.py`
- Create: `telegram_summarizer/handlers.py`
- Create: `tests/test_handlers.py`

- [x] Set up bot with python-telegram-bot (or aiogram, pick one)
- [x] Handle forwarded messages: collect into per-user buffer, extract text and media info
- [x] After forwarding batch (timeout or explicit trigger), show inline keyboard form: processing level (min/mid/max), format (markdown/pdf/docx), save media (yes/no)
- [x] Handle callback queries to update form selections
- [x] On confirm: send status message, call summarizer, call exporter, edit status message with result
- [x] For pdf/docx: send result as file attachment
- [x] For media save=yes with pdf/docx: attach forwarded media files
- [x] Ignore media for markdown format
- [x] Check user limits before processing, reject if exceeded
- [x] Record token usage after successful processing
- [x] Write tests: message collection, form building, callback handling (with mocked bot API)
- [x] Run pytest - must pass before task 6

### Task 6: Docker setup

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`

- [x] Create Dockerfile: Python slim base, install deps, copy code, run with python -m telegram_summarizer
- [x] Create docker-compose.yml: single service, mount `./data` volume for config and SQLite db
- [x] Test docker-compose build succeeds
- [x] Run pytest - must pass before task 7

### Task 7: Verify acceptance criteria

- [x] Manual test: forward messages to bot, select options, receive summary
- [x] Manual test: verify PDF and DOCX output open correctly
- [x] Manual test: verify limits are enforced, user without username is rejected
- [x] Run full test suite: pytest
- [x] Run linter: ruff check . && ruff format --check .
- [x] Verify test coverage meets 80%+

### Task 8: Update documentation

- [x] Update README.md with setup instructions, usage, configuration
- [x] Update CLAUDE.md if internal patterns changed
- [x] Move this plan to `docs/plans/completed/`

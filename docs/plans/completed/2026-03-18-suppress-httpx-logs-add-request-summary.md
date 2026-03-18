# Suppress httpx logs and add request summary logging

## Overview

Suppress noisy httpx INFO-level logs (getUpdates polling) and add a structured summary log line after each summarization request with token counts, message count, parameters, and username.

## Context

- Files involved: `telegram_summarizer/bot.py`, `telegram_summarizer/handlers.py`
- Related patterns: existing `logging.basicConfig` in `bot.py:48-51`, logger usage in `handlers.py`
- Dependencies: none

## Development Approach

- **Testing approach**: Regular (code first, then tests)
- Complete each task fully before moving to the next
- **CRITICAL: every task MUST include new/updated tests**
- **CRITICAL: all tests must pass before starting next task**

## Implementation Steps

### Task 1: Suppress httpx logs

**Files:**
- Modify: `telegram_summarizer/bot.py`

- [x] Add `logging.getLogger("httpx").setLevel(logging.WARNING)` after `logging.basicConfig()` in `run_bot()`
- [x] Write test verifying httpx logger level is set to WARNING after `run_bot` configures logging
- [x] Run project test suite - must pass before task 2

### Task 2: Add request summary logging

**Files:**
- Modify: `telegram_summarizer/handlers.py`

- [x] Add a `logger.info(...)` call in `_process_summary()` after successful summarization (after `record_usage` on line 259) that logs: username, message count, media count, level, format, save_media flag, input_tokens, output_tokens
- [x] Format example: `Summary completed: user=@johndoe messages=5 media=2 level=mid format=pdf save_media=True input_tokens=1234 output_tokens=567`
- [x] Write test for `_process_summary` verifying the log line is emitted with correct fields
- [x] Run project test suite - must pass before task 3

### Task 3: Verify acceptance criteria

- [x] Manual test: run bot, confirm httpx getUpdates lines no longer appear in logs
- [x] Manual test: process a summary, confirm summary log line appears with all fields
- [x] Run full test suite (`pytest`)
- [x] Run linter (`ruff check .` and `ruff format --check .`)

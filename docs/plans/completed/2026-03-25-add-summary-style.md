# Add "Summary" Style to Summarizer

## Overview

Add a new "Summary" style option to the style selection, positioned next to "Keep original". This style will produce a concise summary of the forwarded messages, focusing on extracting and condensing key points rather than preserving original wording or rewriting into a specific format.

## Context

- Files involved: `telegram_summarizer/summarizer.py`, `telegram_summarizer/handlers.py`, `tests/test_summarizer.py`
- Related patterns: existing STYLE_PROMPTS dict and style_labels dict in handlers
- Dependencies: none

## Development Approach

- **Testing approach**: Regular (code first, then tests)
- Complete each task fully before moving to the next
- **CRITICAL: every task MUST include new/updated tests**
- **CRITICAL: all tests must pass before starting next task**

## Implementation Steps

### Task 1: Add "summary" style prompt and UI button

**Files:**
- Modify: `telegram_summarizer/summarizer.py`
- Modify: `telegram_summarizer/handlers.py`

- [x] Add `"summary"` key to `STYLE_PROMPTS` dict in `summarizer.py` with prompt: "Summarize the key points concisely. Remove all chat artifacts, filler, and redundancy. Focus on extracting the most important information and presenting it as a brief, structured summary. Output as a single cohesive document."
- [x] Add `"summary": "Summary"` to `style_labels` dict in `handlers.py`, positioned after "original"
- [x] Update help text in handlers.py to mention the new Summary style
- [x] Write test for summarize() with style="summary" in `tests/test_summarizer.py`
- [x] Run project test suite - must pass before task 2

### Task 2: Verify acceptance criteria

- [x] Manual test: forward messages to bot, select Summary style, verify it produces a concise summary
- [x] Run full test suite (`pytest`)
- [x] Run linter (`ruff check .` and `ruff format --check .`)

### Task 3: Update documentation

- [x] Update CLAUDE.md if style list mentioned
- [x] Move this plan to `docs/plans/completed/`

# Add TLG Output Format

## Overview

Add a new "TLG" output format that sends the summary as a Telegram message with MarkdownV2 formatting and attaches media directly to the message when "Use media" is enabled.

**Behavior:**
- Summary text is converted from standard markdown to Telegram MarkdownV2
- If media is enabled and there are photos, and the text fits in a caption (≤1024 chars): send as photo with caption
- If text is too long for caption or no photos: send text as message, then media separately
- Documents always sent separately (can't be captioned with long text)

## Context

- Files involved: `telegram_summarizer/handlers.py`, `telegram_summarizer/exporter.py`, `tests/test_handlers.py`, `tests/test_exporter.py`
- Current formats: `markdown` (plain text message), `pdf` (file), `docx` (file)
- Format selection: `VALID_FORMATS` set in handlers.py line 13, `format_labels` dict line 58
- Media sending: handlers.py lines 385-391, currently skipped for `markdown` format
- Telegram caption limit: 1024 characters
- Telegram message limit: 4096 characters (already handled as `TELEGRAM_MSG_LIMIT`)

## Development Approach

- **Testing approach**: Regular (code first, then tests)
- Complete each task fully before moving to the next
- **CRITICAL: every task MUST include new/updated tests**
- **CRITICAL: all tests must pass before starting next task**

## Implementation Steps

### Task 1: Add `export_tlg` function in exporter.py

**Files:** `telegram_summarizer/exporter.py`, `tests/test_exporter.py`

- [x] Add `export_tlg(summary_text: str) -> str` function that converts standard markdown to Telegram MarkdownV2:
  - Escape special chars: `_`, `*`, `[`, `]`, `(`, `)`, `~`, `` ` ``, `>`, `#`, `+`, `-`, `=`, `|`, `{`, `}`, `.`, `!`
  - Convert `# Heading` → `*Heading*` (bold)
  - Convert `**bold**` → `*bold*`
  - Convert `_italic_` → `_italic_`
  - Handle bullet lists (`- item` → `• item`)
- [x] Write tests for `export_tlg`: headings, escaping special chars, bullet lists, plain text
- [x] Run tests — must pass before next task

### Task 2: Add TLG format to form UI and validation

**Files:** `telegram_summarizer/handlers.py`, `tests/test_handlers.py`

- [x] Add `"tlg"` to `VALID_FORMATS` set (line 13)
- [x] Add `"tlg": "TLG"` to `format_labels` dict (line 58), position after `"markdown"`
- [x] Update help text to describe TLG format
- [x] Write/update tests for keyboard layout with new TLG button
- [x] Write/update tests for callback data validation with `"tlg"` format
- [x] Run tests — must pass before next task

### Task 3: Implement TLG sending logic in _process_summary

**Files:** `telegram_summarizer/handlers.py`, `tests/test_handlers.py`

- [x] Add `TELEGRAM_CAPTION_LIMIT = 1024` constant
- [x] Add TLG format branch in `_process_summary` (after markdown, before pdf):
  - Call `export_tlg(result.text)` to get MarkdownV2 text
  - If `save_media` and photos exist and text ≤ 1024 chars: send first photo with caption (parse_mode=MarkdownV2), send remaining media separately
  - Otherwise: send text as message with parse_mode=MarkdownV2 (split if >4096), then send media separately if enabled
- [x] Update media sending condition: allow media for TLG format (remove `fmt != "markdown"` check, replace with appropriate logic)
- [x] Write tests for TLG sending: short text with photo (caption), long text with photo (separate), no media, text splitting
- [x] Run tests — must pass before next task

### Task 4: Verify acceptance criteria

- [x] Verify all formats work: markdown, tlg, pdf, docx
- [x] Verify media attachment in TLG: short text → photo caption, long text → separate messages
- [x] Run full test suite
- [x] Run linter (`ruff check .` and `ruff format --check .`)

### Task 5: Update documentation

- [ ] Update README.md to mention TLG format
- [ ] Update CLAUDE.md if format list is mentioned

## Technical Details

**MarkdownV2 escaping rules:**
- All special characters must be escaped with `\` when used literally
- Special chars: `_*[]()~` `` ` `` `>#+\-=|{}.!`
- Inside code blocks (`` ` ``), only `` ` `` and `\` need escaping

**Caption vs message decision tree:**
```
if save_media AND has photos AND len(tlg_text) <= 1024:
    → send first photo with caption=tlg_text, parse_mode=MarkdownV2
    → send remaining photos/docs separately
else:
    → send text as message(s) with parse_mode=MarkdownV2
    → if save_media: send all media separately
```

**Telegram API methods used:**
- `reply_photo(file_id, caption=text, parse_mode="MarkdownV2")` — photo with formatted caption
- `reply_text(text, parse_mode="MarkdownV2")` — formatted text message
- `edit_message_text(text, parse_mode="MarkdownV2")` — edit status to formatted result

## Post-Completion

**Manual verification:**
- Forward messages to test bot, select TLG format, confirm MarkdownV2 renders correctly
- Test with media: short summary → should appear as photo caption
- Test with long summary + media → text first, media after
- Test special characters in summary don't break MarkdownV2 parsing

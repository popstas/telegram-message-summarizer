# Add Summarization Styles

## Overview
- Add a new "Style" dimension to the summarization form with three options: Keep original, Instruction, Blog
- Style is independent from processing level (min/mid/max) — users pick both
- Default style: Instruction
- Style prompts instruct the LLM to clean up chat-like language and produce a cohesive single document
- All style prompts include instruction to remove chat-like words, filler phrases, and informal language

## Context
- Form keyboard: `handlers.py:50-81` (`build_form_keyboard()`)
- Session state: `handlers.py:21-28` (`UserSession` dataclass)
- Callback handler: `handlers.py:228-279` (`callback_handler()`)
- Prompts: `summarizer.py:6-24` (`LEVEL_PROMPTS` dict)
- Summarize function: `summarizer.py:34-55`
- Processing pipeline: `handlers.py:282-374` (`_process_summary()`)
- Help text: `handlers.py:245-262`

## Development Approach
- **Testing approach**: Regular (code first, then tests)
- Complete each task fully before moving to the next
- Make small, focused changes
- **CRITICAL: every task MUST include new/updated tests** for code changes in that task
- **CRITICAL: all tests must pass before starting next task**
- **CRITICAL: update this plan file when scope changes during implementation**
- Run tests after each change
- Maintain backward compatibility

## Testing Strategy
- **Unit tests**: required for every task
- E2E tests exist but require external Telegram API credentials — update if feasible

## Progress Tracking
- Mark completed items with `[x]` immediately when done
- Add newly discovered tasks with ➕ prefix
- Document issues/blockers with ⚠️ prefix
- Update plan if implementation deviates from original scope

## Implementation Steps

### Task 1: Add style prompts to summarizer
- [x] Add `STYLE_PROMPTS` dict in `summarizer.py` with three styles:
  - `original`: "Keep the text close to original wording. Clean up chat artifacts (filler words, informal abbreviations, repeated greetings) but preserve the author's voice and structure. Output as a single cohesive document."
  - `instruction`: "Rewrite as a clear, structured instructional document. Remove all chat-like language, filler words, greetings, and informal phrases. Use imperative or declarative tone. Output as a single cohesive document with logical sections."
  - `blog`: "Rewrite as an engaging blog post. Remove chat artifacts and informal filler. Use a natural, readable narrative style with smooth transitions. Output as a single cohesive document."
- [x] Update `summarize()` function to accept `style` parameter (default: `"instruction"`)
- [x] Combine level prompt + style prompt in agent instructions
- [x] Write tests for `summarize()` with different style values
- [x] Write tests verifying prompt combination logic
- [x] Run tests — must pass before next task

### Task 2: Add style to session and form keyboard
- [x] Add `style: str = "instruction"` field to `UserSession` dataclass
- [x] Add style button row in `build_form_keyboard()` between format and media rows: "Keep original", "Instruction" (default), "Blog"
- [x] Use callback data pattern `style:original/instruction/blog` matching existing patterns
- [x] Mark selected style with brackets like other options
- [x] Write tests for `build_form_keyboard()` with style selection
- [x] Run tests — must pass before next task

### Task 3: Handle style callbacks and pass to processing
- [x] Add `style:` callback handling in `callback_handler()` (same pattern as `level:`, `fmt:`, `media:`)
- [x] Pass `session.style` to `summarize()` call in `_process_summary()`
- [x] Update help text to describe the three styles
- [x] Write tests for callback handler with style callbacks
- [x] Write tests for `_process_summary()` passing style parameter
- [x] Run tests — must pass before next task

### Task 4: Update reprocess to preserve style
- [x] Ensure style is preserved in `_last_processed` session data
- [x] Verify `/reprocess` restores style selection correctly
- [x] Write test for reprocess with style preservation
- [x] Run tests — must pass before next task

### Task 5: Verify acceptance criteria
- [x] Verify all three styles produce different output characteristics
- [x] Verify style works independently with all three levels (9 combinations)
- [x] Verify default style is "instruction"
- [x] Run full test suite (unit tests)
- [x] Run linter (`ruff check .` and `ruff format --check .`) — all issues must be fixed

### Task 6: [Final] Update documentation
- [x] Update README.md if needed
- [x] Update CLAUDE.md if new patterns discovered

## Technical Details

**Style prompt combination with level prompt:**
```
Level instruction (min/mid/max) + "\n\n" + Style instruction (original/instruction/blog)
```

**New callback data values:**
- `style:original`
- `style:instruction`
- `style:blog`

**Keyboard layout (updated):**
```
[ Min ] [ [Mid] ] [ Max ]          ← processing level
[ [MD] ] [ PDF ] [ DOCX ]         ← output format
[ Keep original ] [ [Instruction] ] [ Blog ]  ← NEW: style
[ Use media 📎 ] [ no media ]     ← media toggle
[ ✅ Confirm ] [ ❓ Help ]        ← actions
```

## Post-Completion

**Manual verification:**
- Forward several messages to the bot and test each style visually
- Verify the "Instruction" style effectively removes chat artifacts
- Compare "Blog" output quality with "Keep original"

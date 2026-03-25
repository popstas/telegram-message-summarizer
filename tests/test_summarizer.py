from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from telegram_summarizer.summarizer import LEVEL_PROMPTS, STYLE_PROMPTS, SummaryResult, summarize


def _make_mock_result(output_text="Summary text", input_tokens=100, output_tokens=50):
    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens

    response = MagicMock()
    response.usage = usage

    result = MagicMock()
    result.final_output = output_text
    result.raw_responses = [response]
    return result


@pytest.fixture
def mock_runner():
    with patch("telegram_summarizer.summarizer.Runner") as mock:
        mock.run = AsyncMock()
        yield mock


@pytest.mark.asyncio
async def test_summarize_min_level(mock_runner):
    mock_runner.run.return_value = _make_mock_result("Light summary")

    result = await summarize("Hello world messages", "min")

    assert result.text == "Light summary"
    assert result.input_tokens == 100
    assert result.output_tokens == 50

    agent_arg = mock_runner.run.call_args[0][0]
    assert LEVEL_PROMPTS["min"] in agent_arg.instructions
    assert STYLE_PROMPTS["instruction"] in agent_arg.instructions


@pytest.mark.asyncio
async def test_summarize_mid_level(mock_runner):
    mock_runner.run.return_value = _make_mock_result("Balanced summary")

    result = await summarize("Some messages", "mid")

    assert result.text == "Balanced summary"
    agent_arg = mock_runner.run.call_args[0][0]
    assert LEVEL_PROMPTS["mid"] in agent_arg.instructions


@pytest.mark.asyncio
async def test_summarize_max_level(mock_runner):
    mock_runner.run.return_value = _make_mock_result("Brief summary")

    result = await summarize("Long messages here", "max")

    assert result.text == "Brief summary"
    agent_arg = mock_runner.run.call_args[0][0]
    assert LEVEL_PROMPTS["max"] in agent_arg.instructions


@pytest.mark.asyncio
async def test_summarize_invalid_level(mock_runner):
    with pytest.raises(ValueError, match="Unknown level"):
        await summarize("text", "invalid")


@pytest.mark.asyncio
async def test_summarize_token_counting(mock_runner):
    mock_runner.run.return_value = _make_mock_result("Result", input_tokens=500, output_tokens=200)

    result = await summarize("text", "min")

    assert result.input_tokens == 500
    assert result.output_tokens == 200


@pytest.mark.asyncio
async def test_summarize_multiple_responses(mock_runner):
    usage1 = MagicMock()
    usage1.input_tokens = 100
    usage1.output_tokens = 50

    usage2 = MagicMock()
    usage2.input_tokens = 200
    usage2.output_tokens = 80

    resp1 = MagicMock()
    resp1.usage = usage1
    resp2 = MagicMock()
    resp2.usage = usage2

    result_mock = MagicMock()
    result_mock.final_output = "Final"
    result_mock.raw_responses = [resp1, resp2]
    mock_runner.run.return_value = result_mock

    result = await summarize("text", "mid")

    assert result.text == "Final"
    assert isinstance(result, SummaryResult)
    # Usage.add accumulates tokens from both responses
    assert result.input_tokens == 300
    assert result.output_tokens == 130


@pytest.mark.asyncio
async def test_summarize_uses_configured_model(mock_runner):
    mock_runner.run.return_value = _make_mock_result()

    await summarize("text", "min", model="gpt-5-nano")

    agent_arg = mock_runner.run.call_args[0][0]
    assert agent_arg.model == "gpt-5-nano"


@pytest.mark.asyncio
async def test_summarize_passes_messages_as_input(mock_runner):
    mock_runner.run.return_value = _make_mock_result()

    await summarize("Message 1\nMessage 2\nMessage 3", "mid")

    input_arg = mock_runner.run.call_args[0][1]
    assert input_arg == "Message 1\nMessage 2\nMessage 3"


@pytest.mark.asyncio
async def test_summarize_with_original_style(mock_runner):
    mock_runner.run.return_value = _make_mock_result("Original style output")

    result = await summarize("text", "min", style="original")

    assert result.text == "Original style output"
    agent_arg = mock_runner.run.call_args[0][0]
    assert STYLE_PROMPTS["original"] in agent_arg.instructions
    assert LEVEL_PROMPTS["min"] in agent_arg.instructions


@pytest.mark.asyncio
async def test_summarize_with_blog_style(mock_runner):
    mock_runner.run.return_value = _make_mock_result("Blog style output")

    result = await summarize("text", "mid", style="blog")

    assert result.text == "Blog style output"
    agent_arg = mock_runner.run.call_args[0][0]
    assert STYLE_PROMPTS["blog"] in agent_arg.instructions
    assert LEVEL_PROMPTS["mid"] in agent_arg.instructions


@pytest.mark.asyncio
async def test_summarize_with_summary_style(mock_runner):
    mock_runner.run.return_value = _make_mock_result("Summary style output")

    result = await summarize("text", "mid", style="summary")

    assert result.text == "Summary style output"
    agent_arg = mock_runner.run.call_args[0][0]
    assert STYLE_PROMPTS["summary"] in agent_arg.instructions
    assert LEVEL_PROMPTS["mid"] in agent_arg.instructions


@pytest.mark.asyncio
async def test_summarize_default_style_is_instruction(mock_runner):
    mock_runner.run.return_value = _make_mock_result()

    await summarize("text", "min")

    agent_arg = mock_runner.run.call_args[0][0]
    assert STYLE_PROMPTS["instruction"] in agent_arg.instructions


@pytest.mark.asyncio
async def test_summarize_invalid_style(mock_runner):
    with pytest.raises(ValueError, match="Unknown style"):
        await summarize("text", "min", style="invalid")


@pytest.mark.asyncio
async def test_summarize_prompt_combination(mock_runner):
    mock_runner.run.return_value = _make_mock_result()

    await summarize("text", "max", style="blog")

    agent_arg = mock_runner.run.call_args[0][0]
    expected = LEVEL_PROMPTS["max"] + "\n\n" + STYLE_PROMPTS["blog"]
    assert agent_arg.instructions == expected


def test_all_style_prompts_are_distinct():
    styles = list(STYLE_PROMPTS.values())
    assert len(styles) == 4
    assert len(set(styles)) == 4, "All style prompts must be unique"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "level,style",
    [(level, style) for level in ["min", "mid", "max"] for style in ["original", "summary", "instruction", "blog"]],
)
async def test_all_level_style_combinations(mock_runner, level, style):
    mock_runner.run.return_value = _make_mock_result()

    await summarize("test text", level, style=style)

    agent_arg = mock_runner.run.call_args[0][0]
    expected = LEVEL_PROMPTS[level] + "\n\n" + STYLE_PROMPTS[style]
    assert agent_arg.instructions == expected

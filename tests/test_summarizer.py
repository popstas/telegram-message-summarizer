from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from telegram_summarizer.summarizer import LEVEL_PROMPTS, SummaryResult, summarize


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


@pytest.fixture
def mock_config():
    with patch("telegram_summarizer.summarizer.load_config") as mock:
        mock.return_value = {"openai_model": "gpt-4.1-nano"}
        yield mock


@pytest.mark.asyncio
async def test_summarize_min_level(mock_runner, mock_config):
    mock_runner.run.return_value = _make_mock_result("Light summary")

    result = await summarize("Hello world messages", "min")

    assert result.text == "Light summary"
    assert result.input_tokens == 100
    assert result.output_tokens == 50

    agent_arg = mock_runner.run.call_args[0][0]
    assert agent_arg.instructions == LEVEL_PROMPTS["min"]


@pytest.mark.asyncio
async def test_summarize_mid_level(mock_runner, mock_config):
    mock_runner.run.return_value = _make_mock_result("Balanced summary")

    result = await summarize("Some messages", "mid")

    assert result.text == "Balanced summary"
    agent_arg = mock_runner.run.call_args[0][0]
    assert agent_arg.instructions == LEVEL_PROMPTS["mid"]


@pytest.mark.asyncio
async def test_summarize_max_level(mock_runner, mock_config):
    mock_runner.run.return_value = _make_mock_result("Brief summary")

    result = await summarize("Long messages here", "max")

    assert result.text == "Brief summary"
    agent_arg = mock_runner.run.call_args[0][0]
    assert agent_arg.instructions == LEVEL_PROMPTS["max"]


@pytest.mark.asyncio
async def test_summarize_invalid_level(mock_runner, mock_config):
    with pytest.raises(ValueError, match="Unknown level"):
        await summarize("text", "invalid")


@pytest.mark.asyncio
async def test_summarize_token_counting(mock_runner, mock_config):
    mock_runner.run.return_value = _make_mock_result("Result", input_tokens=500, output_tokens=200)

    result = await summarize("text", "min")

    assert result.input_tokens == 500
    assert result.output_tokens == 200


@pytest.mark.asyncio
async def test_summarize_multiple_responses(mock_runner, mock_config):
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
    # Usage.add is called on real Usage object, so tokens accumulate
    assert isinstance(result, SummaryResult)


@pytest.mark.asyncio
async def test_summarize_uses_configured_model(mock_runner, mock_config):
    mock_config.return_value = {"openai_model": "gpt-5-nano"}
    mock_runner.run.return_value = _make_mock_result()

    await summarize("text", "min")

    agent_arg = mock_runner.run.call_args[0][0]
    assert agent_arg.model == "gpt-5-nano"


@pytest.mark.asyncio
async def test_summarize_passes_messages_as_input(mock_runner, mock_config):
    mock_runner.run.return_value = _make_mock_result()

    await summarize("Message 1\nMessage 2\nMessage 3", "mid")

    input_arg = mock_runner.run.call_args[0][1]
    assert input_arg == "Message 1\nMessage 2\nMessage 3"

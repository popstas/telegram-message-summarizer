from dataclasses import dataclass

from agents import Agent, Runner
from agents.usage import Usage

LEVEL_PROMPTS = {
    "min": (
        "You summarize forwarded Telegram messages. "
        "Keep the summary very close to the original: preserve most quotes and key phrases, "
        "only lightly rewrite for clarity. Use the same language as the original messages."
    ),
    "mid": (
        "You summarize forwarded Telegram messages. "
        "Provide a balanced summary: capture the main points and key details, "
        "paraphrase where appropriate, and omit redundant information. "
        "Use the same language as the original messages."
    ),
    "max": (
        "You summarize forwarded Telegram messages. "
        "Heavily condense the content into the most essential points only. "
        "Be very concise, omit all secondary details and examples. "
        "Use the same language as the original messages."
    ),
}


@dataclass
class SummaryResult:
    text: str
    input_tokens: int
    output_tokens: int


async def summarize(messages_text: str, level: str, model: str = "gpt-4.1-nano") -> SummaryResult:
    if level not in LEVEL_PROMPTS:
        raise ValueError(f"Unknown level: {level}. Must be one of: {', '.join(LEVEL_PROMPTS)}")

    agent = Agent(
        name="Summarizer",
        instructions=LEVEL_PROMPTS[level],
        model=model,
    )

    result = await Runner.run(agent, messages_text)

    total_usage = Usage()
    for response in result.raw_responses:
        if response.usage:
            total_usage.add(response.usage)

    return SummaryResult(
        text=result.final_output,
        input_tokens=total_usage.input_tokens,
        output_tokens=total_usage.output_tokens,
    )

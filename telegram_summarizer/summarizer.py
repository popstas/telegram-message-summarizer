from dataclasses import dataclass

from agents import Agent, Runner
from agents.usage import Usage

STYLE_PROMPTS = {
    "original": (
        "Keep the text close to original wording. Clean up chat artifacts "
        "(filler words, informal abbreviations, repeated greetings) but preserve "
        "the author's voice and structure. Output as a single cohesive document."
    ),
    "instruction": (
        "Rewrite as a clear, structured instructional document. Remove all chat-like "
        "language, filler words, greetings, and informal phrases. Use imperative or "
        "declarative tone. Output as a single cohesive document with logical sections."
    ),
    "blog": (
        "Rewrite as an engaging blog post. Remove chat artifacts and informal filler. "
        "Use a natural, readable narrative style with smooth transitions. "
        "Output as a single cohesive document."
    ),
}

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


async def summarize(
    messages_text: str, level: str, style: str = "instruction", model: str = "gpt-4.1-nano"
) -> SummaryResult:
    if level not in LEVEL_PROMPTS:
        raise ValueError(f"Unknown level: {level}. Must be one of: {', '.join(LEVEL_PROMPTS)}")
    if style not in STYLE_PROMPTS:
        raise ValueError(f"Unknown style: {style}. Must be one of: {', '.join(STYLE_PROMPTS)}")

    instructions = LEVEL_PROMPTS[level] + "\n\n" + STYLE_PROMPTS[style]

    agent = Agent(
        name="Summarizer",
        instructions=instructions,
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

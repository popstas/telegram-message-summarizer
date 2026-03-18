# Telegram Message Summarizer

Telegram bot that summarizes forwarded messages using OpenAI. Forward a batch of messages, choose a processing level and output format, and receive a concise summary.

## Features

- Collect forwarded messages in batches (3-second auto-timeout)
- Three summarization levels: min (light rewrite), mid (balanced), max (heavy condensation)
- Output formats: Markdown, PDF, DOCX
- Per-user token limits (daily, configurable per username)
- Username-based access control
- Interactive inline keyboard for settings

## Setup

### Prerequisites

- Python 3.11+
- Telegram bot token (from [@BotFather](https://t.me/BotFather))
- OpenAI API key

### Local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp data/config.example.yml data/config.yml
# Edit data/config.yml with your bot token and OpenAI API key

python -m telegram_summarizer
```

### Docker

```bash
cp data/config.example.yml data/config.yml
# Edit data/config.yml

docker-compose up
```

## Configuration

Configuration lives in `data/config.yml`. See `data/config.example.yml` for all options.

```yaml
bot_token: "YOUR_BOT_TOKEN"
openai_api_key: "YOUR_OPENAI_API_KEY"
openai_model: "gpt-4.1-nano"

default_limits:
  input_tokens: 10000
  output_tokens: 10000

users:
  some_username:
    limits:
      input_tokens: 50000
      output_tokens: 50000
```

- `bot_token` - Telegram bot token
- `openai_api_key` - OpenAI API key
- `openai_model` - model to use for summarization
- `default_limits` - default daily token limits for all users
- `users` - per-username limit overrides (username without @)

## Usage

1. Forward messages to the bot (one or several)
2. Wait for the batch timeout (3 seconds) or send `/process`
3. Select processing level, output format, and media option via inline keyboard
4. Press Confirm to receive the summary

### Commands

- `/start` - welcome message
- `/stats` - show your token usage statistics
- `/process` - manually trigger processing of collected messages
- `/reprocess` - re-summarize last processed messages with new settings

## Development

```bash
# Run tests
pytest

# Run end-to-end tests (requires test_bot_token in config + Telegram API credentials)
TELEGRAM_API_ID=... TELEGRAM_API_HASH=... pytest -m e2e

# Lint and format check
ruff check .
ruff format --check .
```

## License

MIT

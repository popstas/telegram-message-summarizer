import os

from telegram_summarizer.bot import run_bot
from telegram_summarizer.config import ensure_data_dir, load_config


def main() -> None:
    ensure_data_dir()
    config = load_config()
    if config.get("openai_api_key") and not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = config["openai_api_key"]
    run_bot(config)


if __name__ == "__main__":
    main()

from telegram_summarizer.bot import run_bot
from telegram_summarizer.config import ensure_data_dir


def main() -> None:
    ensure_data_dir()
    run_bot()


if __name__ == "__main__":
    main()

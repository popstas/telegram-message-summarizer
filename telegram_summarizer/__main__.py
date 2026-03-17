from telegram_summarizer.config import ensure_data_dir, load_config


def main() -> None:
    ensure_data_dir()
    config = load_config()
    if not config["bot_token"]:
        print("Error: bot_token not set in data/config.yml")
        return
    # Bot startup will be implemented in Task 5
    print("Bot starting... (not yet implemented)")


if __name__ == "__main__":
    main()

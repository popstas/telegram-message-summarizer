from telegram_summarizer.config import (
    DEFAULT_CONFIG,
    ensure_data_dir,
    get_user_limits,
    load_config,
)


def test_load_config_defaults_when_no_file(tmp_path):
    missing = tmp_path / "nonexistent.yml"
    config = load_config(missing)
    assert config["bot_token"] == ""
    assert config["openai_api_key"] == ""
    assert config["default_limits"]["input_tokens"] == 10000
    assert config["default_limits"]["output_tokens"] == 10000
    assert config["users"] == {}


def test_load_config_from_file(config_file):
    path = config_file(
        {
            "bot_token": "test-token-123",
            "openai_api_key": "sk-test",
            "default_limits": {"input_tokens": 5000},
        }
    )
    config = load_config(path)
    assert config["bot_token"] == "test-token-123"
    assert config["openai_api_key"] == "sk-test"
    assert config["default_limits"]["input_tokens"] == 5000
    # output_tokens should keep default
    assert config["default_limits"]["output_tokens"] == 10000


def test_load_config_with_user_overrides(config_file):
    path = config_file(
        {
            "bot_token": "tok",
            "users": {
                "alice": {"limits": {"input_tokens": 50000, "output_tokens": 50000}},
            },
        }
    )
    config = load_config(path)
    assert config["users"]["alice"]["limits"]["input_tokens"] == 50000


def test_get_user_limits_default(config_file):
    path = config_file({"bot_token": "tok"})
    config = load_config(path)
    limits = get_user_limits(config, "unknown_user")
    assert limits["input_tokens"] == 10000
    assert limits["output_tokens"] == 10000


def test_get_user_limits_with_override(config_file):
    path = config_file(
        {
            "bot_token": "tok",
            "users": {
                "alice": {"limits": {"input_tokens": 99999}},
            },
        }
    )
    config = load_config(path)
    limits = get_user_limits(config, "alice")
    assert limits["input_tokens"] == 99999
    assert limits["output_tokens"] == 10000


def test_ensure_data_dir(tmp_path, monkeypatch):
    import telegram_summarizer.config as config_mod

    new_data_dir = tmp_path / "new_data"
    monkeypatch.setattr(config_mod, "DATA_DIR", new_data_dir)
    assert not new_data_dir.exists()
    ensure_data_dir()
    assert new_data_dir.exists()


def test_load_config_empty_file(tmp_path):
    path = tmp_path / "empty.yml"
    path.write_text("")
    config = load_config(path)
    assert config == DEFAULT_CONFIG

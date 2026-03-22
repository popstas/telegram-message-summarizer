import copy
import os
from pathlib import Path

import yaml

DATA_DIR = Path(os.environ.get("SUMMARIZER_DATA_DIR", "data"))
CONFIG_PATH = DATA_DIR / "config.yml"

DEFAULT_CONFIG = {
    "bot_token": "",
    "openai_api_key": "",
    "openai_model": "gpt-4.1-nano",
    "default_limits": {
        "input_tokens": 10000,
        "output_tokens": 10000,
    },
    "users": {},
    "test_bot_token": "",
    "proxy_url": "",
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: Path | None = None) -> dict:
    if path is None:
        path = CONFIG_PATH
    config = copy.deepcopy(DEFAULT_CONFIG)
    if path.exists():
        with open(path) as f:
            file_config = yaml.safe_load(f) or {}
        config = _deep_merge(config, file_config)
    return config


def get_user_limits(config: dict, username: str) -> dict:
    defaults = config["default_limits"]
    user_overrides = config.get("users", {}).get(username, {}).get("limits", {})
    return {**defaults, **user_overrides}


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

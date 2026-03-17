from datetime import date, timedelta

import pytest

from telegram_summarizer.user_manager import (
    NoUsernameError,
    UserManager,
)


@pytest.fixture
def user_manager(tmp_path):
    return UserManager(db_path=tmp_path / "test_users.db")


@pytest.fixture
def config():
    return {
        "default_limits": {
            "input_tokens": 10000,
            "output_tokens": 10000,
        },
        "users": {
            "vip_user": {
                "limits": {
                    "input_tokens": 50000,
                    "output_tokens": 50000,
                }
            }
        },
    }


class TestNoUsername:
    def test_check_limits_no_username(self, user_manager, config):
        with pytest.raises(NoUsernameError):
            user_manager.check_limits(None, 100, 100, config)

    def test_check_limits_empty_username(self, user_manager, config):
        with pytest.raises(NoUsernameError):
            user_manager.check_limits("", 100, 100, config)

    def test_record_usage_no_username(self, user_manager):
        with pytest.raises(NoUsernameError):
            user_manager.record_usage(None, 100, 100)

    def test_get_stats_no_username(self, user_manager):
        with pytest.raises(NoUsernameError):
            user_manager.get_stats(None)


class TestCheckLimits:
    def test_within_limits(self, user_manager, config):
        assert user_manager.check_limits("testuser", 5000, 5000, config) is True

    def test_exceeds_input_limit(self, user_manager, config):
        user_manager.record_usage("testuser", 9000, 0)
        assert user_manager.check_limits("testuser", 2000, 0, config) is False

    def test_exceeds_output_limit(self, user_manager, config):
        user_manager.record_usage("testuser", 0, 9000)
        assert user_manager.check_limits("testuser", 0, 2000, config) is False

    def test_exactly_at_limit(self, user_manager, config):
        user_manager.record_usage("testuser", 5000, 5000)
        assert user_manager.check_limits("testuser", 5000, 5000, config) is True

    def test_vip_user_higher_limits(self, user_manager, config):
        user_manager.record_usage("vip_user", 9000, 9000)
        assert user_manager.check_limits("vip_user", 2000, 2000, config) is True


class TestRecordUsage:
    def test_record_and_get_stats(self, user_manager):
        user_manager.record_usage("testuser", 100, 200)
        stats = user_manager.get_stats("testuser")
        assert stats["input_tokens_today"] == 100
        assert stats["output_tokens_today"] == 200
        assert stats["input_tokens_total"] == 100
        assert stats["output_tokens_total"] == 200

    def test_accumulates_usage(self, user_manager):
        user_manager.record_usage("testuser", 100, 200)
        user_manager.record_usage("testuser", 300, 400)
        stats = user_manager.get_stats("testuser")
        assert stats["input_tokens_today"] == 400
        assert stats["output_tokens_today"] == 600
        assert stats["input_tokens_total"] == 400
        assert stats["output_tokens_total"] == 600


class TestDailyReset:
    def test_resets_daily_counters(self, user_manager):
        user_manager.record_usage("testuser", 5000, 3000)

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        with user_manager._get_conn() as conn:
            conn.execute(
                "UPDATE users SET last_reset_date = ? WHERE username = ?",
                (yesterday, "testuser"),
            )

        stats = user_manager.get_stats("testuser")
        assert stats["input_tokens_today"] == 0
        assert stats["output_tokens_today"] == 0
        assert stats["input_tokens_total"] == 5000
        assert stats["output_tokens_total"] == 3000
        assert stats["last_reset_date"] == date.today().isoformat()


class TestGetStats:
    def test_new_user_stats(self, user_manager):
        stats = user_manager.get_stats("newuser")
        assert stats["username"] == "newuser"
        assert stats["input_tokens_today"] == 0
        assert stats["output_tokens_today"] == 0
        assert stats["input_tokens_total"] == 0
        assert stats["output_tokens_total"] == 0

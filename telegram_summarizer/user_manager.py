import sqlite3
from datetime import date
from pathlib import Path

from telegram_summarizer.config import DATA_DIR


class NoUsernameError(Exception):
    pass


class LimitExceededError(Exception):
    pass


class UserManager:
    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            db_path = DATA_DIR / "users.db"
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    input_tokens_today INTEGER NOT NULL DEFAULT 0,
                    output_tokens_today INTEGER NOT NULL DEFAULT 0,
                    input_tokens_total INTEGER NOT NULL DEFAULT 0,
                    output_tokens_total INTEGER NOT NULL DEFAULT 0,
                    last_reset_date TEXT NOT NULL
                )
            """)

    def _ensure_user(self, conn: sqlite3.Connection, username: str) -> None:
        conn.execute(
            """
            INSERT OR IGNORE INTO users (username, last_reset_date)
            VALUES (?, ?)
            """,
            (username, date.today().isoformat()),
        )

    def _maybe_reset_daily(self, conn: sqlite3.Connection, username: str) -> None:
        row = conn.execute("SELECT last_reset_date FROM users WHERE username = ?", (username,)).fetchone()
        if row and row["last_reset_date"] != date.today().isoformat():
            conn.execute(
                """
                UPDATE users
                SET input_tokens_today = 0, output_tokens_today = 0,
                    last_reset_date = ?
                WHERE username = ?
                """,
                (date.today().isoformat(), username),
            )

    def check_limits(
        self,
        username: str | None,
        input_tokens: int,
        output_tokens: int,
        config: dict,
    ) -> bool:
        if not username:
            raise NoUsernameError("User must have a Telegram username")

        from telegram_summarizer.config import get_user_limits

        limits = get_user_limits(config, username)

        with self._get_conn() as conn:
            self._ensure_user(conn, username)
            self._maybe_reset_daily(conn, username)
            row = conn.execute(
                "SELECT input_tokens_today, output_tokens_today FROM users WHERE username = ?",
                (username,),
            ).fetchone()

        current_input = row["input_tokens_today"] if row else 0
        current_output = row["output_tokens_today"] if row else 0

        if current_input + input_tokens > limits["input_tokens"]:
            return False
        if current_output + output_tokens > limits["output_tokens"]:
            return False
        return True

    def record_usage(self, username: str | None, input_tokens: int, output_tokens: int) -> None:
        if not username:
            raise NoUsernameError("User must have a Telegram username")

        with self._get_conn() as conn:
            self._ensure_user(conn, username)
            self._maybe_reset_daily(conn, username)
            conn.execute(
                """
                UPDATE users
                SET input_tokens_today = input_tokens_today + ?,
                    output_tokens_today = output_tokens_today + ?,
                    input_tokens_total = input_tokens_total + ?,
                    output_tokens_total = output_tokens_total + ?
                WHERE username = ?
                """,
                (input_tokens, output_tokens, input_tokens, output_tokens, username),
            )

    def get_stats(self, username: str | None) -> dict:
        if not username:
            raise NoUsernameError("User must have a Telegram username")

        with self._get_conn() as conn:
            self._ensure_user(conn, username)
            self._maybe_reset_daily(conn, username)
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        return {
            "username": row["username"],
            "input_tokens_today": row["input_tokens_today"],
            "output_tokens_today": row["output_tokens_today"],
            "input_tokens_total": row["input_tokens_total"],
            "output_tokens_total": row["output_tokens_total"],
            "last_reset_date": row["last_reset_date"],
        }

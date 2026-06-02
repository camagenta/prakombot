"""Env config for the notifier service.

Singleton pattern, mirrors prakombot/config.py so both services
behave consistently and tests can reset state cleanly.
"""
import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str) -> int:
    raw = os.getenv(name)
    if not raw:
        return 0
    return int(raw)


class Config:
    """Singleton env config for the notifier service."""

    _instance: Optional["Config"] = None

    def __new__(cls) -> "Config":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or ""
            inst.telegram_chat_id = _int_env("TELEGRAM_CHAT_ID")
            inst.telegram_thread_id = _int_env("TELEGRAM_THREAD_ID")
            inst.telegram_parse_mode = os.getenv("TELEGRAM_PARSE_MODE") or "HTML"
            inst.webhook_secret = os.getenv("WEBHOOK_SECRET") or ""
            inst.webhook_host = os.getenv("WEBHOOK_HOST") or "0.0.0.0"
            inst.webhook_port = _int_env("WEBHOOK_PORT") or 8000
            inst.telegram_api_base = (
                os.getenv("TELEGRAM_API_BASE") or "https://api.telegram.org"
            )
            inst.telegram_max_retries = _int_env("TELEGRAM_MAX_RETRIES") or 3
            inst.telegram_retry_base_seconds = _int_env("TELEGRAM_RETRY_BASE_SECONDS") or 1
            cls._instance = inst
        return cls._instance

    def validate(self) -> None:
        """Raise if any required env is missing.

        Optional in production code paths (e.g. tests); call at startup
        to fail fast.
        """
        missing = []
        if not self.telegram_bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.telegram_chat_id:
            missing.append("TELEGRAM_CHAT_ID")
        if not self.webhook_secret:
            missing.append("WEBHOOK_SECRET")
        if missing:
            raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

    @classmethod
    def _reset_for_test(cls) -> None:
        cls._instance = None

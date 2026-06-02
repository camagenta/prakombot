import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _load_int_list(val: Optional[str]) -> list[int]:
    if not val:
        return []
    return [int(x.strip()) for x in val.split(",") if x.strip()]


def _int_env(name: str) -> int:
    """Parse int from env, treating None and empty string as 0.

    Fix for B2: previous code did `int(os.getenv("X", "0"))` which crashes
    when the env var is SET to "" (empty string) rather than missing.
    """
    raw = os.getenv(name)
    if not raw:
        return 0
    return int(raw)


class Config:
    """Singleton config object.

    Fix for B1: previous code was a `@dataclass` with `default_factory`
    reading env vars, so every `Config()` call re-parsed the environment.
    That was wasteful and made behavior depend on env mutations between
    calls. Now: env is parsed once on first instantiation and cached.

    Tests can call `Config._reset_for_test()` to clear the cache.
    """

    _instance: Optional["Config"] = None

    def __new__(cls) -> "Config":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst.bot_token = os.getenv("BOT_TOKEN") or ""
            inst.bot_username = os.getenv("BOT_USERNAME") or ""
            inst.api_id = _int_env("API_ID")
            inst.api_hash = os.getenv("API_HASH") or ""
            inst.group_id = _int_env("GROUP_ID")
            inst.admin_ids = _load_int_list(os.getenv("ADMIN_IDS"))
            cls._instance = inst
        return cls._instance

    def validate_bot(self) -> None:
        missing = []
        if not self.bot_token:
            missing.append("BOT_TOKEN")
        if not self.group_id:
            missing.append("GROUP_ID")
        if missing:
            raise RuntimeError(f"Missing bot env vars: {', '.join(missing)}")

    def validate_broadcast(self) -> None:
        missing = []
        if not self.api_id:
            missing.append("API_ID")
        if not self.api_hash:
            missing.append("API_HASH")
        if not self.group_id:
            missing.append("GROUP_ID")
        if not self.bot_username:
            missing.append("BOT_USERNAME")
        if missing:
            raise RuntimeError(f"Missing broadcast env vars: {', '.join(missing)}")

    @classmethod
    def _reset_for_test(cls) -> None:
        """Clear the cached singleton. Used by tests to start from a clean slate."""
        cls._instance = None

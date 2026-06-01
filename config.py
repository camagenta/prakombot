import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _load_int_list(val: str | None) -> list[int]:
    if not val:
        return []
    return [int(x.strip()) for x in val.split(",") if x.strip()]


@dataclass
class Config:
    bot_token: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    bot_username: str = field(default_factory=lambda: os.getenv("BOT_USERNAME", ""))
    api_id: int = field(default_factory=lambda: int(os.getenv("API_ID", "0")))
    api_hash: str = field(default_factory=lambda: os.getenv("API_HASH", ""))
    group_id: int = field(default_factory=lambda: int(os.getenv("GROUP_ID", "0")))
    admin_ids: list[int] = field(
        default_factory=lambda: _load_int_list(os.getenv("ADMIN_IDS"))
    )

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

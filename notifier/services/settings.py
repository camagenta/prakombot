"""Phase 2 stub: manage group settings (name, description, permissions, slow mode)."""
from typing import Protocol


class GroupSettingsService(Protocol):
    def set_name(self, chat_id: int, name: str) -> dict:
        ...

    def set_description(self, chat_id: int, description: str) -> dict:
        ...

    def set_slow_mode(self, chat_id: int, seconds: int) -> dict:
        ...

    def set_permissions(self, chat_id: int, permissions: dict) -> dict:
        ...


class NotImplementedGroupSettingsService:
    def set_name(self, chat_id: int, name: str) -> dict:
        raise NotImplementedError("GroupSettingsService.set_name — Phase 2")

    def set_description(self, chat_id: int, description: str) -> dict:
        raise NotImplementedError("GroupSettingsService.set_description — Phase 2")

    def set_slow_mode(self, chat_id: int, seconds: int) -> dict:
        raise NotImplementedError("GroupSettingsService.set_slow_mode — Phase 2")

    def set_permissions(self, chat_id: int, permissions: dict) -> dict:
        raise NotImplementedError("GroupSettingsService.set_permissions — Phase 2")


_default: GroupSettingsService | None = None


def get_settings_service() -> GroupSettingsService:
    global _default
    if _default is None:
        _default = NotImplementedGroupSettingsService()
    return _default

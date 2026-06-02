"""Phase 2 stub: auto-reply to common questions in the group."""
from typing import Protocol


class AutoReplyService(Protocol):
    def register(self, pattern: str, response: str) -> None:
        ...

    def unregister(self, pattern: str) -> None:
        ...

    def reply_if_match(self, text: str) -> str | None:
        ...


class NotImplementedAutoReplyService:
    def register(self, pattern: str, response: str) -> None:
        raise NotImplementedError("AutoReplyService.register — Phase 2")

    def unregister(self, pattern: str) -> None:
        raise NotImplementedError("AutoReplyService.unregister — Phase 2")

    def reply_if_match(self, text: str) -> str | None:
        raise NotImplementedError("AutoReplyService.reply_if_match — Phase 2")


_default: AutoReplyService | None = None


def get_autoreply_service() -> AutoReplyService:
    global _default
    if _default is None:
        _default = NotImplementedAutoReplyService()
    return _default

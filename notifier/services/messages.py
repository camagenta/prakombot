"""Phase 2 stub: send, edit, delete, pin messages in a Telegram group."""
from typing import Protocol


class MessageService(Protocol):
    def send(self, chat_id: int, text: str, thread_id: int = 0) -> dict:
        ...

    def edit(self, chat_id: int, message_id: int, text: str) -> dict:
        ...

    def delete(self, chat_id: int, message_id: int) -> dict:
        ...

    def pin(self, chat_id: int, message_id: int) -> dict:
        ...

    def unpin(self, chat_id: int, message_id: int) -> dict:
        ...


class NotImplementedMessageService:
    def send(self, chat_id: int, text: str, thread_id: int = 0) -> dict:
        raise NotImplementedError("MessageService.send — Phase 2")

    def edit(self, chat_id: int, message_id: int, text: str) -> dict:
        raise NotImplementedError("MessageService.edit — Phase 2")

    def delete(self, chat_id: int, message_id: int) -> dict:
        raise NotImplementedError("MessageService.delete — Phase 2")

    def pin(self, chat_id: int, message_id: int) -> dict:
        raise NotImplementedError("MessageService.pin — Phase 2")

    def unpin(self, chat_id: int, message_id: int) -> dict:
        raise NotImplementedError("MessageService.unpin — Phase 2")


_default: MessageService | None = None


def get_message_service() -> MessageService:
    global _default
    if _default is None:
        _default = NotImplementedMessageService()
    return _default

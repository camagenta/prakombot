"""Phase 2 stub: manage forum topics in a Telegram supergroup.

Phase 1: NotImplementedTopicService raises NotImplementedError on every call.
Phase 2: swap in a real implementation that calls the Telegram Bot API
(createForumTopic, editForumTopic, closeForumTopic, reopenForumTopic,
deleteForumTopic, editGeneralForumTopic, closeGeneralForumTopic,
reopenGeneralForumTopic, unpinAllChatMessages, etc.).
"""
from typing import Protocol


class TopicService(Protocol):
    def create_topic(self, chat_id: int, name: str, icon_color: int = 0) -> dict:
        ...

    def edit_topic(self, chat_id: int, message_thread_id: int, name: str) -> dict:
        ...

    def close_topic(self, chat_id: int, message_thread_id: int) -> dict:
        ...

    def reopen_topic(self, chat_id: int, message_thread_id: int) -> dict:
        ...

    def delete_topic(self, chat_id: int, message_thread_id: int) -> dict:
        ...


class NotImplementedTopicService:
    def create_topic(self, chat_id: int, name: str, icon_color: int = 0) -> dict:
        raise NotImplementedError("TopicService.create_topic — Phase 2")

    def edit_topic(self, chat_id: int, message_thread_id: int, name: str) -> dict:
        raise NotImplementedError("TopicService.edit_topic — Phase 2")

    def close_topic(self, chat_id: int, message_thread_id: int) -> dict:
        raise NotImplementedError("TopicService.close_topic — Phase 2")

    def reopen_topic(self, chat_id: int, message_thread_id: int) -> dict:
        raise NotImplementedError("TopicService.reopen_topic — Phase 2")

    def delete_topic(self, chat_id: int, message_thread_id: int) -> dict:
        raise NotImplementedError("TopicService.delete_topic — Phase 2")


_default: TopicService | None = None


def get_topic_service() -> TopicService:
    global _default
    if _default is None:
        _default = NotImplementedTopicService()
    return _default

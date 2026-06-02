"""Phase 2 stub: manage group members (kick, ban, unban, promote, demote)."""
from typing import Protocol


class MemberService(Protocol):
    def ban(self, chat_id: int, user_id: int, until_date: int = 0) -> dict:
        ...

    def unban(self, chat_id: int, user_id: int) -> dict:
        ...

    def kick(self, chat_id: int, user_id: int) -> dict:
        ...

    def promote(self, chat_id: int, user_id: int, can_post: bool = True) -> dict:
        ...

    def demote(self, chat_id: int, user_id: int) -> dict:
        ...


class NotImplementedMemberService:
    def ban(self, chat_id: int, user_id: int, until_date: int = 0) -> dict:
        raise NotImplementedError("MemberService.ban — Phase 2")

    def unban(self, chat_id: int, user_id: int) -> dict:
        raise NotImplementedError("MemberService.unban — Phase 2")

    def kick(self, chat_id: int, user_id: int) -> dict:
        raise NotImplementedError("MemberService.kick — Phase 2")

    def promote(self, chat_id: int, user_id: int, can_post: bool = True) -> dict:
        raise NotImplementedError("MemberService.promote — Phase 2")

    def demote(self, chat_id: int, user_id: int) -> dict:
        raise NotImplementedError("MemberService.demote — Phase 2")


_default: MemberService | None = None


def get_member_service() -> MemberService:
    global _default
    if _default is None:
        _default = NotImplementedMemberService()
    return _default

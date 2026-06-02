"""
Tests for bot.py confirm_handler — covers B4 (race) and B5 (wrong fallback).

B4: rapid double-click on "✅ Ya, Kirim" must not insert a duplicate DB row
    and must not call Telegram API twice.

B5: if approve_chat_join_request raises, decline_chat_join_request must NOT
    be called as a "fallback". A failed approve is a failed verification,
    not a reversal of the user's intent.
"""
import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, call

REPO = "/Volumes/Pusdiklat BPS 4/Antigravity/prakombot"
if REPO not in sys.path:
    sys.path.insert(0, REPO)

# Ensure conftest mocks are loaded
from tests.conftest import _make_module  # noqa: E401  (side-effect: populates sys.modules)


def _make_update_context(callback_data: str = "confirm"):
    """Build a fake Update + Context for confirm_handler."""
    query = MagicMock()
    query.data = callback_data
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()

    update = MagicMock()
    update.callback_query = query
    update.effective_user = MagicMock()
    update.effective_user.id = 12345
    update.effective_user.full_name = "Test User"
    update.effective_user.username = "tester"

    context = MagicMock()
    context.user_data = {
        "nama": "Test User",
        "nip": "123456789012345678",
        "instansi": "Test Instansi",
        "jenjang": "Mahir",
        "file_id": "AgAC-file-id",
    }
    context.bot = MagicMock()
    context.bot.approve_chat_join_request = AsyncMock()
    context.bot.decline_chat_join_request = AsyncMock()
    context.bot.send_message = AsyncMock()
    context.bot.send_document = AsyncMock()
    return update, context


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestConfirmHandlerFallback(unittest.TestCase):
    """B5: confirm_handler must NOT call decline when approve raises."""

    def setUp(self):
        # Set up env so Config validates
        os.environ["BOT_TOKEN"] = "x:1"
        os.environ["GROUP_ID"] = "-1001"
        os.environ["ADMIN_IDS"] = ""
        if "config" in sys.modules:
            import importlib
            importlib.reload(sys.modules["config"])
            sys.modules["config"].Config._reset_for_test()
        # Now import bot
        if "bot" in sys.modules:
            import importlib
            importlib.reload(sys.modules["bot"])

    def test_approve_failure_does_not_call_decline(self):
        """If approve raises, decline must NOT be called."""
        from bot import confirm_handler

        update, context = _make_update_context("confirm")
        context.bot.approve_chat_join_request.side_effect = RuntimeError("API error")
        with patch("bot.save_verification", new=AsyncMock(return_value=42)), \
             patch("bot.update_status", new=AsyncMock()) as mock_update_status, \
             patch("bot._forward_to_admins", new=AsyncMock()):
            result = _run(confirm_handler(update, context))

        context.bot.approve_chat_join_request.assert_awaited_once()
        context.bot.decline_chat_join_request.assert_not_called()
        self.assertEqual(result, -1)

    def test_approve_success_marks_approved(self):
        """Happy path: approve success → status='approved'."""
        from bot import confirm_handler

        update, context = _make_update_context("confirm")
        with patch("bot.save_verification", new=AsyncMock(return_value=42)), \
             patch("bot.update_status", new=AsyncMock()) as mock_update_status, \
             patch("bot._forward_to_admins", new=AsyncMock()):
            result = _run(confirm_handler(update, context))

        context.bot.approve_chat_join_request.assert_awaited_once()
        context.bot.decline_chat_join_request.assert_not_called()
        mock_update_status.assert_awaited_once_with(42, "approved")
        self.assertEqual(result, -1)


class TestConfirmHandlerRace(unittest.TestCase):
    """B4: rapid re-entry of confirm_handler must not duplicate work."""

    def setUp(self):
        os.environ["BOT_TOKEN"] = "x:1"
        os.environ["GROUP_ID"] = "-1001"
        os.environ["ADMIN_IDS"] = ""
        if "config" in sys.modules:
            import importlib
            importlib.reload(sys.modules["config"])
            sys.modules["config"].Config._reset_for_test()
        if "bot" in sys.modules:
            import importlib
            importlib.reload(sys.modules["bot"])

    def test_second_call_after_user_data_clear_is_noop(self):
        """After first call clears user_data, second call must be a no-op:
        - no DB insert
        - no approve API call
        - responds to second callback (no crash)"""
        from bot import confirm_handler

        # First call
        update1, context1 = _make_update_context("confirm")
        # Simulate that the first call already cleared user_data (mimics the bug)
        context1.user_data.clear()

        # Second call (user_data is empty → would normally KeyError)
        update2, context2 = _make_update_context("confirm")
        context2.user_data.clear()

        save_mock = AsyncMock(return_value=42)
        update_status_mock = AsyncMock()
        forward_mock = AsyncMock()

        with patch("bot.save_verification", new=save_mock), \
             patch("bot.update_status", new=update_status_mock), \
             patch("bot._forward_to_admins", new=forward_mock):
            # Second call first (race scenario: two clicks arrive back-to-back)
            # Both see empty user_data
            try:
                _run(confirm_handler(update2, context2))
            except (KeyError, AttributeError) as e:
                self.fail(
                    f"Second call crashed with {type(e).__name__}: {e}. "
                    f"Should be a graceful no-op."
                )
            # If the first call had data, it would proceed; but it doesn't, so this
            # tests the "stale state" path: user_data already cleared by something else.

        # The fix should make the second call a no-op when data is missing
        save_mock.assert_not_called()
        update2.callback_query.answer.assert_awaited()  # callback acknowledged

    def test_double_click_does_not_duplicate_db_row(self):
        """Simulated double-click: same context (same user_data store),
        two separate Update objects (one per callback click)."""
        from bot import confirm_handler

        first_update, context = _make_update_context("confirm")
        second_update = MagicMock()
        second_update.callback_query = MagicMock()
        second_update.callback_query.data = "confirm"
        second_update.callback_query.answer = AsyncMock()
        second_update.callback_query.edit_message_text = AsyncMock()
        second_update.effective_user = first_update.effective_user

        save_mock = AsyncMock(return_value=42)
        update_status_mock = AsyncMock()
        forward_mock = AsyncMock()

        with patch("bot.save_verification", new=save_mock), \
             patch("bot.update_status", new=update_status_mock), \
             patch("bot._forward_to_admins", new=forward_mock):
            _run(confirm_handler(first_update, context))
            _run(confirm_handler(second_update, context))

        self.assertEqual(
            save_mock.await_count, 1,
            f"save_verification should be called exactly once. "
            f"Got {save_mock.await_count} calls.",
        )
        self.assertEqual(
            context.bot.approve_chat_join_request.await_count, 1,
            f"approve_chat_join_request should be called exactly once across both clicks.",
        )


if __name__ == "__main__":
    unittest.main()

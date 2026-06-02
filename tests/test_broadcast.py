"""
Tests for broadcast.py — covers B3 (sent-user filter scope).

The bug: broadcast.py line 130 used ALL-TIME sent history, so a user
DM'd on day N who never verified was skipped on day N+1.

The fix: filter should be scoped to TODAY (the broadcast run's date),
so users who never completed verification get re-DM'd on later days.

We extract `_filter_today_batch` as a pure function for unit testing.
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

REPO = "/Volumes/Pusdiklat BPS 4/Antigravity/prakombot"
if REPO not in sys.path:
    sys.path.insert(0, REPO)

# Import via conftest (injects mocked telegram/telethon/httpx modules).
from tests.conftest import _make_module  # noqa: E401  (for type clarity)

# Re-import broadcast with mocks already in sys.modules
import importlib
import broadcast
importlib.reload(broadcast)


def _u(uid: int) -> dict:
    return {"user": {"id": uid, "first_name": f"u{uid}"}}


class TestTodayBatchFilter(unittest.TestCase):
    """B3: filter must scope 'sent' to today only, not all-time."""

    def test_user_dm_3_days_ago_is_resent_today(self):
        """User DM'd 3 days ago, never verified → must be in today's batch."""
        pending = [_u(42)]
        log = [
            {"date": "2026-05-30", "user_id": 42, "status": "sent"},
        ]
        out = broadcast._filter_today_batch(pending, log, today="2026-06-02")
        ids = [r["user"]["id"] for r in out]
        self.assertIn(
            42, ids,
            f"User 42 was DM'd 2026-05-30 (3 days ago) but never verified. "
            f"Should be re-included in today's batch. Got ids={ids}",
        )

    def test_user_dm_today_is_skipped_today(self):
        """Sanity: user DM'd today should be skipped (no double-DM same day)."""
        pending = [_u(42)]
        log = [
            {"date": "2026-06-02", "user_id": 42, "status": "sent"},
        ]
        out = broadcast._filter_today_batch(pending, log, today="2026-06-02")
        ids = [r["user"]["id"] for r in out]
        self.assertNotIn(
            42, ids,
            f"User 42 was DM'd today. Should be skipped to avoid double-DM. "
            f"Got ids={ids}",
        )

    def test_user_with_failed_status_yesterday_is_resent(self):
        """User with status 'failed' yesterday → should be retried today."""
        pending = [_u(99)]
        log = [
            {"date": "2026-06-01", "user_id": 99, "status": "failed", "error": "timeout"},
        ]
        out = broadcast._filter_today_batch(pending, log, today="2026-06-02")
        ids = [r["user"]["id"] for r in out]
        self.assertIn(99, ids)

    def test_blocked_user_today_is_still_skipped(self):
        """User blocked today → skip (no point retrying same day)."""
        pending = [_u(7)]
        log = [
            {"date": "2026-06-02", "user_id": 7, "status": "blocked"},
        ]
        out = broadcast._filter_today_batch(pending, log, today="2026-06-02")
        ids = [r["user"]["id"] for r in out]
        self.assertNotIn(7, ids)

    def test_mixed_history_filters_correctly(self):
        """Mixed: some old, some today, some new."""
        pending = [_u(1), _u(2), _u(3), _u(4)]
        log = [
            {"date": "2026-05-30", "user_id": 1, "status": "sent"},   # old → resend
            {"date": "2026-06-01", "user_id": 2, "status": "sent"},   # yesterday → resend
            {"date": "2026-06-02", "user_id": 3, "status": "sent"},   # today → skip
            # user 4 has no history
        ]
        out = broadcast._filter_today_batch(pending, log, today="2026-06-02")
        ids = sorted(r["user"]["id"] for r in out)
        self.assertEqual(ids, [1, 2, 4])


if __name__ == "__main__":
    unittest.main()

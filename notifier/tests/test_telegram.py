"""Tests for notifier/services/telegram.py.

Covers:
- Correct URL construction
- 5xx/429 triggers retry with backoff
- 401/400 raises (no retry — these are not transient)
- Connection error triggers retry
- After max retries, raises last error
"""
import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch


from notifier.tests.conftest import _make_module


class TestTelegramService(unittest.TestCase):
    def setUp(self):
        import notifier.services.telegram
        import importlib
        importlib.reload(notifier.services.telegram)
        self.tg = notifier.services.telegram

        os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
        os.environ["TELEGRAM_CHAT_ID"] = "-1001"
        os.environ["TELEGRAM_THREAD_ID"] = "25"
        os.environ["TELEGRAM_MAX_RETRIES"] = "3"
        os.environ["TELEGRAM_RETRY_BASE_SECONDS"] = "0"  # no sleep in tests

    def tearDown(self):
        for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_THREAD_ID",
                  "TELEGRAM_MAX_RETRIES", "TELEGRAM_RETRY_BASE_SECONDS"):
            os.environ.pop(k, None)

    def _make_response(self, status_code=200, json_body=None, raise_status=False):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_body or {"ok": True, "result": {"message_id": 42}}
        if raise_status:
            resp.raise_for_status.side_effect = self.tg.TelegramAPIError(f"HTTP {status_code}")
        else:
            resp.raise_for_status = MagicMock()
        return resp

    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_send_to_topic_calls_correct_url(self):
        service = self.tg.TelegramService(bot_token="test-token", api_base="https://api.telegram.org")
        with patch.object(self.tg.httpx, "AsyncClient") as mock_httpx:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=self._make_response())
            mock_httpx.return_value = mock_client

            result = self._run(service.send_to_topic(
                chat_id=-1001, thread_id=25, text="hello"
            ))

            call_args = mock_client.post.call_args
            url = call_args[0][0]
            self.assertIn("api.telegram.org", url)
            self.assertIn("sendMessage", url)
            self.assertIn("chat_id=-1001", url)
            self.assertIn("message_thread_id=25", url)
            self.assertEqual(result["message_id"], 42)

    def test_5xx_triggers_retry_then_succeeds(self):
        service = self.tg.TelegramService(bot_token="test-token", max_retries=3, retry_base_seconds=0)
        with patch.object(self.tg.httpx, "AsyncClient") as mock_httpx:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=[
                self._make_response(status_code=503, raise_status=True),
                self._make_response(status_code=502, raise_status=True),
                self._make_response(status_code=200),
            ])
            mock_httpx.return_value = mock_client

            result = self._run(service.send_to_topic(chat_id=-1001, thread_id=25, text="x"))
            self.assertEqual(result["message_id"], 42)
            self.assertEqual(mock_client.post.await_count, 3)

    def test_429_triggers_retry(self):
        service = self.tg.TelegramService(bot_token="test-token", max_retries=2, retry_base_seconds=0)
        with patch.object(self.tg.httpx, "AsyncClient") as mock_httpx:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=[
                self._make_response(status_code=429, raise_status=True),
                self._make_response(status_code=200),
            ])
            mock_httpx.return_value = mock_client

            result = self._run(service.send_to_topic(chat_id=-1001, thread_id=25, text="x"))
            self.assertEqual(result["message_id"], 42)
            self.assertEqual(mock_client.post.await_count, 2)

    def test_401_does_not_retry(self):
        service = self.tg.TelegramService(bot_token="bad-token", max_retries=3, retry_base_seconds=0)
        with patch.object(self.tg.httpx, "AsyncClient") as mock_httpx:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=self._make_response(
                status_code=401, raise_status=True
            ))
            mock_httpx.return_value = mock_client

            with self.assertRaises(self.tg.TelegramAPIError):
                self._run(service.send_to_topic(chat_id=-1001, thread_id=25, text="x"))
            self.assertEqual(mock_client.post.await_count, 1)

    def test_400_does_not_retry(self):
        service = self.tg.TelegramService(bot_token="test-token", max_retries=3, retry_base_seconds=0)
        with patch.object(self.tg.httpx, "AsyncClient") as mock_httpx:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=self._make_response(
                status_code=400, raise_status=True
            ))
            mock_httpx.return_value = mock_client

            with self.assertRaises(self.tg.TelegramAPIError):
                self._run(service.send_to_topic(chat_id=-1001, thread_id=25, text="x"))
            self.assertEqual(mock_client.post.await_count, 1)

    def test_connection_error_triggers_retry_then_succeeds(self):
        service = self.tg.TelegramService(bot_token="test-token", max_retries=3, retry_base_seconds=0)
        with patch.object(self.tg.httpx, "AsyncClient") as mock_httpx:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            conn_error = self.tg.httpx.HTTPError("connection refused")
            mock_client.post = AsyncMock(side_effect=[
                conn_error,
                conn_error,
                self._make_response(status_code=200),
            ])
            mock_httpx.return_value = mock_client

            result = self._run(service.send_to_topic(chat_id=-1001, thread_id=25, text="x"))
            self.assertEqual(result["message_id"], 42)
            self.assertEqual(mock_client.post.await_count, 3)

    def test_max_retries_exhausted_raises(self):
        service = self.tg.TelegramService(bot_token="test-token", max_retries=2, retry_base_seconds=0)
        with patch.object(self.tg.httpx, "AsyncClient") as mock_httpx:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=self._make_response(
                status_code=500, raise_status=True
            ))
            mock_httpx.return_value = mock_client

            with self.assertRaises(self.tg.TelegramAPIError):
                self._run(service.send_to_topic(chat_id=-1001, thread_id=25, text="x"))
            self.assertEqual(mock_client.post.await_count, 2)


class TestTelegramServiceFactory(unittest.TestCase):
    def test_factory_returns_singleton(self):
        import notifier.services.telegram
        import importlib
        importlib.reload(notifier.services.telegram)
        a = notifier.services.telegram.get_telegram_service()
        b = notifier.services.telegram.get_telegram_service()
        self.assertIs(a, b)

    def test_factory_uses_config_when_not_provided(self):
        import notifier.services.telegram
        from notifier.config import Config
        import importlib
        importlib.reload(notifier.services.telegram)
        Config._reset_for_test()
        os.environ["TELEGRAM_BOT_TOKEN"] = "from-config"
        try:
            notifier.services.telegram._default_service = None
            svc = notifier.services.telegram.get_telegram_service()
            self.assertEqual(svc.bot_token, "from-config")
        finally:
            os.environ.pop("TELEGRAM_BOT_TOKEN", None)
            notifier.services.telegram._default_service = None
            Config._reset_for_test()


if __name__ == "__main__":
    unittest.main()

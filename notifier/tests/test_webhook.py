"""Tests for notifier/routes/webhook.py and notifier/routes/health.py.

Covers:
- S1: Valid signature + valid payload → 200, message sent
- S2: Missing signature → 401
- S3: Bad signature → 401
- S4: Malformed JSON / missing fields → 422
- S5: Telegram 429 → 500 (after retries exhausted)
- S6: Telegram 401 → 500
- S7: Concurrent submissions → all handled
- S8: /healthz → 200 {"status": "ok"}
- S9: Config regression — env change between calls
"""
import asyncio
import hashlib
import hmac
import json
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch


REPO = "/Volumes/Pusdiklat BPS 4/Antigravity/prakombot"
if REPO not in sys.path:
    sys.path.insert(0, REPO)


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _valid_payload(form_id: str = "form-1") -> dict:
    return {
        "form_id": form_id,
        "submitted_at": "2025-01-15T10:30:00Z",
        "responses": [
            {"index": 0, "title": "Nama", "answer": "Budi"},
            {"index": 1, "title": "NIP", "answer": "12345"},
        ],
    }


class TestWebhookHappyPath(unittest.TestCase):
    def setUp(self):
        import notifier.tests.conftest  # force-install httpx with HTTPError
        os.environ["WEBHOOK_SECRET"] = "test-secret"
        os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
        os.environ["TELEGRAM_CHAT_ID"] = "-1001"
        from notifier.config import Config
        Config._reset_for_test()

    def tearDown(self):
        for k in ("WEBHOOK_SECRET", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
            os.environ.pop(k, None)
        from notifier.config import Config
        Config._reset_for_test()

    def test_s1_valid_sig_and_payload_returns_200(self):
        from notifier.routes import webhook
        body = json.dumps(_valid_payload()).encode()
        sig = _sign(body, "test-secret")

        fake_tg = MagicMock()
        fake_tg.send_to_topic = AsyncMock(return_value={"message_id": 99})

        result = _run(webhook.process_form_submit(body, sig, telegram=fake_tg))
        self.assertEqual(result["status"], 200)
        fake_tg.send_to_topic.assert_awaited_once()
        sent_text = fake_tg.send_to_topic.await_args.kwargs.get("text") or \
                    fake_tg.send_to_topic.await_args.args[0]
        self.assertIn("Budi", sent_text)
        self.assertIn("12345", sent_text)

    def test_s2_missing_signature_returns_401(self):
        from notifier.routes import webhook
        body = json.dumps(_valid_payload()).encode()
        result = _run(webhook.process_form_submit(body, None, telegram=MagicMock()))
        self.assertEqual(result["status"], 401)

    def test_s3_bad_signature_returns_401(self):
        from notifier.routes import webhook
        body = json.dumps(_valid_payload()).encode()
        result = _run(webhook.process_form_submit(body, "deadbeef" * 8, telegram=MagicMock()))
        self.assertEqual(result["status"], 401)

    def test_s4_malformed_json_returns_422(self):
        from notifier.routes import webhook
        body = b"{not valid json"
        sig = _sign(body, "test-secret")
        result = _run(webhook.process_form_submit(body, sig, telegram=MagicMock()))
        self.assertEqual(result["status"], 422)

    def test_s4b_missing_form_id_returns_422(self):
        from notifier.routes import webhook
        payload = _valid_payload()
        del payload["form_id"]
        body = json.dumps(payload).encode()
        sig = _sign(body, "test-secret")
        result = _run(webhook.process_form_submit(body, sig, telegram=MagicMock()))
        self.assertEqual(result["status"], 422)

    def test_s5_telegram_429_returns_500(self):
        from notifier.routes import webhook
        from notifier.services.telegram import TelegramAPIError
        body = json.dumps(_valid_payload()).encode()
        sig = _sign(body, "test-secret")

        fake_tg = MagicMock()
        fake_tg.send_to_topic = AsyncMock(side_effect=TelegramAPIError("429 exhausted"))

        result = _run(webhook.process_form_submit(body, sig, telegram=fake_tg))
        self.assertEqual(result["status"], 500)

    def test_s6_telegram_401_returns_500(self):
        from notifier.routes import webhook
        from notifier.services.telegram import TelegramAPIError
        body = json.dumps(_valid_payload()).encode()
        sig = _sign(body, "test-secret")

        fake_tg = MagicMock()
        fake_tg.send_to_topic = AsyncMock(side_effect=TelegramAPIError("401 bad token"))

        result = _run(webhook.process_form_submit(body, sig, telegram=fake_tg))
        self.assertEqual(result["status"], 500)

    def test_s7_concurrent_submissions_all_handled(self):
        from notifier.routes import webhook

        async def run_all():
            tasks = []
            for i in range(5):
                body = json.dumps(_valid_payload(form_id=f"form-{i}")).encode()
                sig = _sign(body, "test-secret")
                fake_tg = MagicMock()
                fake_tg.send_to_topic = AsyncMock(return_value={"message_id": i})
                tasks.append(webhook.process_form_submit(body, sig, telegram=fake_tg))
            return await asyncio.gather(*tasks)

        loop = asyncio.new_event_loop()
        try:
            results = loop.run_until_complete(run_all())
        finally:
            loop.close()
        self.assertEqual(len(results), 5)
        for r in results:
            self.assertEqual(r["status"], 200)


class TestHealthEndpoint(unittest.TestCase):
    def test_s8_healthz_returns_ok(self):
        from notifier.routes import health
        result = health.healthz()
        self.assertEqual(result, {"status": "ok"})


class TestConfigRegression(unittest.TestCase):
    def test_s9_env_change_does_not_break_subsequent_calls(self):
        import notifier.tests.conftest  # force-install httpx mock
        from notifier.routes import webhook
        os.environ["WEBHOOK_SECRET"] = "secret-1"
        from notifier.config import Config
        Config._reset_for_test()

        body1 = json.dumps(_valid_payload("form-a")).encode()
        sig1 = _sign(body1, "secret-1")
        fake_tg1 = MagicMock()
        fake_tg1.send_to_topic = AsyncMock(return_value={"message_id": 1})
        r1 = _run(webhook.process_form_submit(body1, sig1, telegram=fake_tg1))
        self.assertEqual(r1["status"], 200)

        os.environ["WEBHOOK_SECRET"] = "secret-2"
        Config._reset_for_test()

        body2 = json.dumps(_valid_payload("form-b")).encode()
        sig2 = _sign(body2, "secret-2")
        fake_tg2 = MagicMock()
        fake_tg2.send_to_topic = AsyncMock(return_value={"message_id": 2})
        r2 = _run(webhook.process_form_submit(body2, sig2, telegram=fake_tg2))
        self.assertEqual(r2["status"], 200)

        Config._reset_for_test()


if __name__ == "__main__":
    unittest.main()

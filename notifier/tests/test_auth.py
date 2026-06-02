"""Tests for notifier/auth.py — HMAC-SHA256 signature verification.

GAS computes HMAC-SHA256 of the request body using a shared secret
and sets it as the X-Signature header. Python verifies with the same
secret. The body is the raw bytes (not the parsed JSON).
"""
import hashlib
import hmac
import os
import sys
import unittest


REPO = "/Volumes/Pusdiklat BPS 4/Antigravity/prakombot"
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from tests.conftest import _make_module  # noqa: E401  (side-effect: sys.modules mocks)


SECRET = "test-secret-key-1234567890abcdef"


def _sign(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class TestVerifySignature(unittest.TestCase):
    def setUp(self):
        import notifier.auth
        importlib = __import__("importlib")
        importlib.reload(notifier.auth)
        self.auth = notifier.auth
        os.environ["WEBHOOK_SECRET"] = SECRET

    def tearDown(self):
        os.environ.pop("WEBHOOK_SECRET", None)

    def test_valid_signature_returns_body(self):
        body = b'{"hello":"world"}'
        sig = _sign(body)
        result = self.auth.verify_signature(body, sig)
        self.assertEqual(result, body)

    def test_missing_signature_header_raises(self):
        body = b'{"hello":"world"}'
        with self.assertRaises(self.auth.AuthError) as ctx:
            self.auth.verify_signature(body, None)
        self.assertIn("missing", str(ctx.exception).lower())

    def test_empty_signature_header_raises(self):
        body = b'{"hello":"world"}'
        with self.assertRaises(self.auth.AuthError):
            self.auth.verify_signature(body, "")

    def test_bad_signature_raises(self):
        body = b'{"hello":"world"}'
        with self.assertRaises(self.auth.AuthError) as ctx:
            self.auth.verify_signature(body, "deadbeef" * 8)
        self.assertIn("invalid", str(ctx.exception).lower())

    def test_wrong_secret_raises(self):
        body = b'{"hello":"world"}'
        sig = _sign(body, secret="other-secret")
        with self.assertRaises(self.auth.AuthError):
            self.auth.verify_signature(body, sig)

    def test_tampered_body_raises(self):
        original = b'{"amount":100}'
        sig = _sign(original)
        tampered = b'{"amount":999}'
        with self.assertRaises(self.auth.AuthError):
            self.auth.verify_signature(tampered, sig)

    def test_no_secret_configured_raises(self):
        os.environ.pop("WEBHOOK_SECRET", None)
        body = b'{"hello":"world"}'
        sig = _sign(body, secret=SECRET)
        with self.assertRaises(self.auth.AuthError) as ctx:
            self.auth.verify_signature(body, sig)
        self.assertIn("not configured", str(ctx.exception).lower())


class TestSigningHelper(unittest.TestCase):
    def setUp(self):
        import notifier.auth
        importlib = __import__("importlib")
        importlib.reload(notifier.auth)
        self.auth = notifier.auth

    def test_compute_signature_matches_hmac(self):
        body = b"test-body"
        result = self.auth.compute_signature(body, "my-secret")
        expected = hmac.new(b"my-secret", body, hashlib.sha256).hexdigest()
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()

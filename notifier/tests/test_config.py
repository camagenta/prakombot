"""Tests for notifier/config.py — singleton + safe int env parsing.

Mirrors the prakombot/tests/test_config.py contract: Config is a
singleton, and empty env strings do not raise.
"""
import importlib
import os
import sys
import unittest


REPO = "/Volumes/Pusdiklat BPS 4/Antigravity/prakombot"
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from tests.conftest import _make_module  # noqa: E401  (side-effect: sys.modules mocks)


class _EnvGuard:
    def __enter__(self):
        self._saved = dict(os.environ)
        return self
    def __exit__(self, *a):
        os.environ.clear()
        os.environ.update(self._saved)


def _reload_config():
    if "notifier.config" in sys.modules:
        cfg_mod = importlib.reload(sys.modules["notifier.config"])
    else:
        import notifier.config  # noqa: F401
        cfg_mod = sys.modules["notifier.config"]
    cfg_mod.Config._reset_for_test()
    return cfg_mod


class TestConfigSingleton(unittest.TestCase):
    def setUp(self):
        _reload_config()

    def test_repeated_instantiation_returns_same_instance(self):
        with _EnvGuard():
            os.environ["TELEGRAM_BOT_TOKEN"] = "x:1"
            os.environ["TELEGRAM_CHAT_ID"] = "-1001"
            cfg_mod = _reload_config()
            self.assertIs(cfg_mod.Config(), cfg_mod.Config())

    def test_env_change_does_not_leak(self):
        with _EnvGuard():
            os.environ["TELEGRAM_BOT_TOKEN"] = "first"
            cfg_mod = _reload_config()
            first = cfg_mod.Config()
            os.environ["TELEGRAM_BOT_TOKEN"] = "second"
            second = cfg_mod.Config()
            self.assertEqual(first.telegram_bot_token, second.telegram_bot_token)


class TestConfigIntSafety(unittest.TestCase):
    def setUp(self):
        _reload_config()

    def test_empty_chat_id_does_not_crash(self):
        with _EnvGuard():
            os.environ["TELEGRAM_CHAT_ID"] = ""
            os.environ["TELEGRAM_BOT_TOKEN"] = "x:1"
            cfg_mod = _reload_config()
            try:
                c = cfg_mod.Config()
            except ValueError as e:
                self.fail(f"Config() raised on empty TELEGRAM_CHAT_ID: {e}")
            self.assertEqual(c.telegram_chat_id, 0)

    def test_empty_thread_id_does_not_crash(self):
        with _EnvGuard():
            os.environ["TELEGRAM_THREAD_ID"] = ""
            cfg_mod = _reload_config()
            c = cfg_mod.Config()
            self.assertEqual(c.telegram_thread_id, 0)

    def test_valid_chat_id_parsed(self):
        with _EnvGuard():
            os.environ["TELEGRAM_CHAT_ID"] = "-1001936999792"
            os.environ["TELEGRAM_THREAD_ID"] = "25"
            cfg_mod = _reload_config()
            c = cfg_mod.Config()
            self.assertEqual(c.telegram_chat_id, -1001936999792)
            self.assertEqual(c.telegram_thread_id, 25)


class TestConfigDefaults(unittest.TestCase):
    def setUp(self):
        _reload_config()

    def test_default_webhook_port_is_8000(self):
        with _EnvGuard():
            for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_THREAD_ID",
                      "WEBHOOK_SECRET", "WEBHOOK_PORT", "WEBHOOK_HOST"):
                os.environ.pop(k, None)
            cfg_mod = _reload_config()
            c = cfg_mod.Config()
            self.assertEqual(c.webhook_port, 8000)
            self.assertEqual(c.webhook_host, "0.0.0.0")

    def test_custom_webhook_port(self):
        with _EnvGuard():
            os.environ["WEBHOOK_PORT"] = "9000"
            cfg_mod = _reload_config()
            c = cfg_mod.Config()
            self.assertEqual(c.webhook_port, 9000)


if __name__ == "__main__":
    unittest.main()

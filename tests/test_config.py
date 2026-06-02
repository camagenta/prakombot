"""
Tests for config.py — covers B1 (singleton) and B2 (safe int parsing).

RED → GREEN contract:
- B1: `Config()` must return the same instance on repeated calls.
- B2: empty GROUP_ID / API_ID env vars must not raise; treat as 0.
"""
import importlib
import os
import sys
import unittest
from unittest.mock import patch


REPO = "/Volumes/Pusdiklat BPS 4/Antigravity/prakombot"
if REPO not in sys.path:
    sys.path.insert(0, REPO)


class _EnvGuard:
    """Snapshot/restore os.environ around each test."""
    def __enter__(self):
        self._saved = dict(os.environ)
        return self
    def __exit__(self, *a):
        os.environ.clear()
        os.environ.update(self._saved)


def _reload_config():
    """Force re-import of config with current env, clearing any cached singleton."""
    if "config" in sys.modules:
        cfg_mod = importlib.reload(sys.modules["config"])
    else:
        import config  # noqa: F401
        cfg_mod = sys.modules["config"]
    cfg_mod.Config._reset_for_test()
    return cfg_mod


class TestConfigSingleton(unittest.TestCase):
    """B1: Config dataclass must not reload env on every instantiation."""

    def setUp(self):
        _reload_config()  # clear singleton before each test

    def test_repeated_instantiation_returns_same_instance(self):
        with _EnvGuard():
            os.environ["BOT_TOKEN"] = "x:1"
            os.environ["GROUP_ID"] = "-1001"
            cfg_mod = _reload_config()
            a = cfg_mod.Config()
            b = cfg_mod.Config()
            self.assertIs(
                a, b,
                f"Config() returned different instances: {id(a)} vs {id(b)}. "
                "Should be a singleton to avoid env-reload and to behave consistently.",
            )

    def test_env_change_does_not_leak_into_existing_instance(self):
        """B1 corollary: a singleton should reflect env at first read, not mutate on change."""
        with _EnvGuard():
            os.environ["BOT_TOKEN"] = "first"
            cfg_mod = _reload_config()
            first = cfg_mod.Config()
            os.environ["BOT_TOKEN"] = "second"
            second = cfg_mod.Config()
            self.assertEqual(
                first.bot_token, second.bot_token,
                "Singleton must cache; otherwise calls get inconsistent values.",
            )


class TestConfigIntSafety(unittest.TestCase):
    """B2: empty GROUP_ID / API_ID env must not raise ValueError."""

    def test_empty_group_id_does_not_crash(self):
        """B2 actual scenario: env var is SET to empty string (e.g. in .env file)."""
        with _EnvGuard():
            os.environ["GROUP_ID"] = ""  # empty string, not missing
            os.environ["BOT_TOKEN"] = "x:1"
            cfg_mod = _reload_config()
            try:
                c = cfg_mod.Config()
            except ValueError as e:
                self.fail(f"Config() raised ValueError on empty GROUP_ID: {e}")
            self.assertEqual(c.group_id, 0, f"Expected 0, got {c.group_id}")

    def test_empty_api_id_does_not_crash(self):
        """B2 actual scenario: env var is SET to empty string."""
        with _EnvGuard():
            os.environ["API_ID"] = ""
            cfg_mod = _reload_config()
            try:
                c = cfg_mod.Config()
            except ValueError as e:
                self.fail(f"Config() raised ValueError on empty API_ID: {e}")
            self.assertEqual(c.api_id, 0, f"Expected 0, got {c.api_id}")

    def test_missing_group_id_does_not_crash(self):
        """Sanity: missing env var should also be 0, not crash."""
        with _EnvGuard():
            os.environ.pop("GROUP_ID", None)
            cfg_mod = _reload_config()
            c = cfg_mod.Config()
            self.assertEqual(c.group_id, 0)

    def test_explicit_zero_group_id_works(self):
        with _EnvGuard():
            os.environ["GROUP_ID"] = "0"
            cfg_mod = _reload_config()
            c = cfg_mod.Config()
            self.assertEqual(c.group_id, 0)

    def test_valid_group_id_parsed(self):
        with _EnvGuard():
            os.environ["GROUP_ID"] = "-1001234567890"
            cfg_mod = _reload_config()
            c = cfg_mod.Config()
            self.assertEqual(c.group_id, -1001234567890)


if __name__ == "__main__":
    unittest.main()

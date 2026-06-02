"""
Test conftest: injects mock modules into sys.modules BEFORE tests import
the modules under test. This lets us test bot.py and broadcast.py logic
without needing telegram/aiosqlite/telethon/httpx to be installed.

Pattern: see https://docs.python.org/3/library/unittest.mock.html
"""
import sys
import types
from unittest.mock import MagicMock


def _make_module(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


# --- telegram.* ---
tg = _make_module("telegram")

class _Stub:
    def __init__(self, *a, **kw): pass

tg.InlineKeyboardButton = _Stub
tg.InlineKeyboardMarkup = _Stub
tg.Update = _Stub

tg_constants = _make_module("telegram.constants")
class _ParseMode:
    MARKDOWN = "md"
    HTML = "html"
tg_constants.ParseMode = _ParseMode

tg_ext = _make_module("telegram.ext")
for cls_name in [
    "Application",
    "CallbackQueryHandler",
    "ChatJoinRequestHandler",
    "CommandHandler",
    "ContextTypes",
    "MessageHandler",
    "filters",
]:
    setattr(tg_ext, cls_name, _Stub)
class _ConversationHandler:
    END = -1
tg_ext.ConversationHandler = _ConversationHandler
# filters is used as filters.TEXT etc — give it a MagicMock
tg_ext.filters = MagicMock()

# --- aiosqlite ---
aiosqlite_mod = _make_module("aiosqlite")
aiosqlite_mod.connect = MagicMock()

# --- telethon ---
telethon_mod = _make_module("telethon")
telethon_mod.TelegramClient = MagicMock

telethon_errors = _make_module("telethon.errors")
class _FloodWaitError(Exception):
    seconds: int = 5
class _UserIsBlockedError(Exception): pass
class _UserPrivacyRestrictedError(Exception): pass
telethon_errors.FloodWaitError = _FloodWaitError
telethon_errors.UserIsBlockedError = _UserIsBlockedError
telethon_errors.UserPrivacyRestrictedError = _UserPrivacyRestrictedError

# --- httpx ---
httpx_mod = _make_module("httpx")
class _AsyncClient:
    def __init__(self, *a, **kw): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass
    async def post(self, *a, **kw):
        m = MagicMock()
        m.raise_for_status = MagicMock()
        m.json.return_value = {"ok": True, "result": []}
        return m
httpx_mod.AsyncClient = _AsyncClient

# --- dotenv (real, but silent) ---
# Already present or installed; do nothing special.

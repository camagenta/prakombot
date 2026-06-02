"""Test conftest: inject mock modules into sys.modules before tests
import notifier modules.

The notifier service uses raw httpx (not python-telegram-bot) to call
the Telegram Bot API, so we only need to mock httpx.
"""
import sys
import types
from unittest.mock import MagicMock


def _make_module(name: str) -> types.ModuleType:
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


# --- httpx (used by notifier.services.telegram) ---
# Always install — notifier's mock has HTTPError, prakombot's doesn't.
httpx_mod = _make_module("httpx")

class _AsyncClient:
    def __init__(self, *a, **kw): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass
    async def post(self, *a, **kw):
        m = MagicMock()
        m.raise_for_status = MagicMock()
        m.json.return_value = {"ok": True, "result": {"message_id": 1}}
        m.status_code = 200
        return m
    async def get(self, *a, **kw):
        m = MagicMock()
        m.raise_for_status = MagicMock()
        m.json.return_value = {"ok": True, "result": []}
        m.status_code = 200
        return m

httpx_mod.AsyncClient = _AsyncClient
class _HTTPError(Exception):
    pass
httpx_mod.HTTPError = _HTTPError

# --- pydantic (used by notifier.schemas) ---
# Only inject a stub if pydantic genuinely cannot be imported.
try:
    import pydantic as _pyd_check
    del _pyd_check
except ImportError:
    pyd_mod = _make_module("pydantic")
    class _BaseModel:
        def __init__(self, **data):
            for k, v in data.items():
                setattr(self, k, v)
    pyd_mod.BaseModel = _BaseModel
    pyd_mod.Field = lambda *a, **kw: None
    pyd_mod.field_validator = lambda *a, **kw: lambda f: f

# --- fastapi (used by notifier.app / routes) ---
if "fastapi" not in sys.modules:
    fa_mod = _make_module("fastapi")
    fa_mod.FastAPI = MagicMock
    fa_mod.HTTPException = type("HTTPException", (Exception,), {"status_code": 500})
    fa_mod.Header = lambda *a, **kw: None
    fa_mod.Request = MagicMock
    fa_mod.status = types.ModuleType("fastapi.status")
    for code in ("HTTP_200_OK", "HTTP_401_UNAUTHORIZED", "HTTP_422_UNPROCESSABLE_ENTITY",
                 "HTTP_400_BAD_REQUEST", "HTTP_500_INTERNAL_SERVER_ERROR"):
        setattr(fa_mod.status, code, code)
    sys.modules["fastapi.status"] = fa_mod.status

if "uvicorn" not in sys.modules:
    uvicorn_mod = _make_module("uvicorn")
    uvicorn_mod.run = MagicMock()

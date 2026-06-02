"""Webhook route handler.

Core function `process_form_submit` is the testable surface — it takes
raw bytes + signature, returns a structured result. The FastAPI route
`handle_form_submit` is a thin wrapper that reads the body and returns
the result.
"""
import json
import logging
from typing import Optional

from ..auth import AuthError, verify_signature
from ..config import Config
from ..schemas import FormSubmitPayload
from ..services.telegram import TelegramAPIError, TelegramService

logger = logging.getLogger(__name__)


async def process_form_submit(
    body: bytes,
    signature: Optional[str],
    telegram: Optional[TelegramService] = None,
) -> dict:
    """Process a form submission webhook.

    Returns: {"status": int, "body": dict}
    Status codes: 200 (success), 401 (bad/missing sig), 422 (bad payload),
    500 (telegram failed).
    """
    if not signature:
        logger.warning("Webhook called with missing signature")
        return {"status": 401, "body": {"error": "missing signature"}}

    try:
        verify_signature(body, signature)
    except AuthError as e:
        logger.warning("Webhook signature verification failed: %s", e)
        return {"status": 401, "body": {"error": "bad signature"}}

    try:
        raw = json.loads(body)
        payload = FormSubmitPayload(**raw)
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("Webhook payload parse failed: %s", e)
        return {"status": 422, "body": {"error": "malformed payload", "detail": str(e)}}
    except Exception as e:  # pydantic ValidationError or other
        logger.warning("Webhook payload validation failed: %s", e)
        return {"status": 422, "body": {"error": "invalid payload", "detail": str(e)}}

    svc = telegram if telegram is not None else TelegramService(
        bot_token=Config().telegram_bot_token,
        default_chat_id=Config().telegram_chat_id,
        default_thread_id=Config().telegram_thread_id,
    )

    try:
        result = await svc.send_to_topic(text=payload.format_message())
    except TelegramAPIError as e:
        logger.error("Telegram send failed: %s", e)
        return {"status": 500, "body": {"error": "telegram failed", "detail": str(e)}}

    return {
        "status": 200,
        "body": {"ok": True, "message_id": result.get("message_id")},
    }


async def handle_form_submit(request, x_signature: Optional[str] = None):
    """FastAPI route handler. Thin wrapper around process_form_submit."""
    body = await request.body()
    result = await process_form_submit(body, x_signature)
    from fastapi.responses import JSONResponse
    return JSONResponse(content=result["body"], status_code=result["status"])

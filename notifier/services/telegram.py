"""Telegram Bot API client used by the notifier service.

Raw httpx, not python-telegram-bot — keeps the dep tree small and
the call sites explicit. Supports retry on transient errors
(5xx, 429, network) and a hard fail on permanent errors (401, 400).
"""
import asyncio
import logging
from typing import Optional
from urllib.parse import quote

import httpx

from ..config import Config

logger = logging.getLogger(__name__)


class TelegramAPIError(Exception):
    """Raised when the Telegram API returns a non-retryable error
    or when retries are exhausted."""


class TelegramService:
    def __init__(
        self,
        bot_token: str,
        api_base: str = "https://api.telegram.org",
        default_chat_id: int = 0,
        default_thread_id: int = 0,
        parse_mode: str = "HTML",
        max_retries: int = 3,
        retry_base_seconds: float = 1.0,
    ):
        self.bot_token = bot_token
        self.api_base = api_base.rstrip("/")
        self.default_chat_id = default_chat_id
        self.default_thread_id = default_thread_id
        self.parse_mode = parse_mode
        self.max_retries = max_retries
        self.retry_base_seconds = retry_base_seconds

    async def send_to_topic(
        self,
        text: str,
        chat_id: Optional[int] = None,
        thread_id: Optional[int] = None,
    ) -> dict:
        """Send a message to a forum topic. Returns Telegram's result
        payload (containing `message_id` on success).

        Retries on 429 and 5xx with exponential backoff. Raises
        TelegramAPIError immediately on 4xx (other than 429) since
        these won't recover.
        """
        use_chat = chat_id if chat_id is not None else self.default_chat_id
        use_thread = thread_id if thread_id is not None else self.default_thread_id
        if not use_chat:
            raise TelegramAPIError("chat_id is required (none provided and no default)")

        encoded = quote(text, safe="")
        url = (
            f"{self.api_base}/bot{self.bot_token}/sendMessage"
            f"?chat_id={use_chat}"
            f"&text={encoded}"
            f"&parse_mode={self.parse_mode}"
        )
        if use_thread:
            url += f"&message_thread_id={use_thread}"

        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(url)
                    if resp.status_code == 401 or resp.status_code == 400:
                        logger.error(
                            "Telegram API permanent error: status=%d body=%s",
                            resp.status_code, resp.text,
                        )
                        raise TelegramAPIError(
                            f"Telegram API returned {resp.status_code}: {resp.text}"
                        )
                    if resp.status_code == 429 or 500 <= resp.status_code < 600:
                        last_exc = TelegramAPIError(f"HTTP {resp.status_code}")
                        if attempt < self.max_retries:
                            delay = self.retry_base_seconds * (2 ** (attempt - 1))
                            logger.warning(
                                "Telegram API transient error %d, retrying in %.1fs (attempt %d/%d)",
                                resp.status_code, delay, attempt, self.max_retries,
                            )
                            await asyncio.sleep(delay)
                            continue
                        raise TelegramAPIError(
                            f"Max retries exhausted on HTTP {resp.status_code}"
                        )
                    resp.raise_for_status()
                    return resp.json().get("result", {})
            except httpx.HTTPError as e:
                last_exc = e
                if attempt < self.max_retries:
                    delay = self.retry_base_seconds * (2 ** (attempt - 1))
                    logger.warning(
                        "Telegram API network error, retrying in %.1fs (attempt %d/%d): %s",
                        delay, attempt, self.max_retries, e,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.error("Telegram API network error after %d attempts: %s", attempt, e)
                raise TelegramAPIError(f"Network error after {attempt} attempts: {e}") from e

        raise TelegramAPIError(f"Failed to send to Telegram: {last_exc}")


_default_service: Optional[TelegramService] = None


def get_telegram_service() -> TelegramService:
    """Module-level singleton. Pulls from Config on first call."""
    global _default_service
    if _default_service is None:
        cfg = Config()
        _default_service = TelegramService(
            bot_token=cfg.telegram_bot_token,
            api_base=cfg.telegram_api_base,
            default_chat_id=cfg.telegram_chat_id,
            default_thread_id=cfg.telegram_thread_id,
            parse_mode=cfg.telegram_parse_mode,
            max_retries=cfg.telegram_max_retries,
            retry_base_seconds=cfg.telegram_retry_base_seconds,
        )
    return _default_service

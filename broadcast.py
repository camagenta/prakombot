#!/usr/bin/env python3
"""
Broadcast script: reads pending join requests via Bot API,
then sends DMs via Telethon (user account).

Usage:
    python broadcast.py              # Send up to daily limit
    python broadcast.py --stats      # Show pending count + today's stats
    python broadcast.py --reset-log  # Reset broadcast log
"""

import asyncio
import json
import logging
import random
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    UserIsBlockedError,
    UserPrivacyRestrictedError,
)

from config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

LOG_FILE = Path("broadcast_log.json")
MAX_DM_PER_DAY = 10
MIN_DELAY = 3.0
MAX_DELAY = 5.0


# ── Log helpers ──────────────────────────────────────────────────────────────


def load_log() -> list[dict[str, Any]]:
    if not LOG_FILE.exists():
        return []
    try:
        with open(LOG_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError):
        return []


def today_entries(log: list[dict[str, Any]]) -> list[dict[str, Any]]:
    today = date.today().isoformat()
    return [e for e in log if e.get("date") == today]


def append_log(entry: dict[str, Any]) -> None:
    log = load_log()
    log.append(entry)
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


# ── Bot API: get pending join requests ───────────────────────────────────────


async def get_pending_requests(bot_token: str, chat_id: int) -> list[dict[str, Any]]:
    """Fetch pending join requests via Bot API getChatJoinRequests."""
    url = f"https://api.telegram.org/bot{bot_token}/getChatJoinRequests"
    params: dict[str, Any] = {"chat_id": chat_id, "limit": 100}
    all_requests: list[dict[str, Any]] = []
    offset = 0

    async with httpx.AsyncClient(timeout=30) as http:
        while True:
            params["offset"] = offset
            resp = await http.post(url, json=params)
            resp.raise_for_status()
            result = resp.json()
            if not result.get("ok"):
                logger.error("Bot API error: %s", result)
                break
            requests = result.get("result", [])
            if not requests:
                break
            all_requests.extend(requests)
            if len(requests) < 100:
                break
            offset += 100

    logger.info("Total pending join requests: %d", len(all_requests))
    return all_requests


# ── DM builder ────────────────────────────────────────────────────────────────


def build_dm_text(bot_username: str) -> str:  # noqa: E501
    return (
        "Halo! 👋\n\n"
        "Kami mendeteksi Anda mengirimkan permintaan bergabung ke grup Prakom.\n"
        "Untuk menyelesaikan proses verifikasi, silakan klik link di bawah:\n\n"
        f"https://t.me/{bot_username}?start=verify\n\n"
        "Setelah verifikasi selesai, request Anda akan di-approve secara otomatis.\n\n"
        "Terima kasih!"
    )


# ── Batch selection ───────────────────────────────────────────────────────────


def _filter_today_batch(
    pending: list[dict[str, Any]],
    log: list[dict[str, Any]],
    today: str,
) -> list[dict[str, Any]]:
    """Return pending requests that should be DM'd today.

    Skips users who already received a DM today (any status), to avoid
    double-DM on the same day. Users DM'd on previous days are included
    again so non-completers get re-contacted on later days.
    """
    sent_today_ids = {
        e["user_id"]
        for e in log
        if e.get("date") == today
    }
    return [r for r in pending if r["user"]["id"] not in sent_today_ids]


# ── Main broadcast ────────────────────────────────────────────────────────────


async def broadcast() -> None:
    cfg = Config()
    cfg.validate_broadcast()

    # 1. Get pending requests via Bot API
    pending = await get_pending_requests(cfg.bot_token, cfg.group_id)

    if not pending:
        logger.info("No pending join requests. Nothing to do.")
        return

    # 2. Filter out users already DM'd today
    log = load_log()
    today = date.today().isoformat()
    to_send = _filter_today_batch(pending, log, today)
    skipped = len(pending) - len(to_send)
    if skipped:
        logger.info("Skipping %d already-DM'd-today user(s).", skipped)

    if not to_send:
        logger.info("All pending users already contacted today.")
        return

    # 3. Daily limit
    today_sent = len([e for e in today_entries(log) if e.get("status") == "sent"])
    remaining = MAX_DM_PER_DAY - today_sent
    if remaining <= 0:
        logger.warning("Daily DM limit (%d) reached. Try again tomorrow.", MAX_DM_PER_DAY)
        return

    batch = to_send[:remaining]
    logger.info(
        "Will send %d DM(s) today (limit: %d, sent today: %d).",
        len(batch), MAX_DM_PER_DAY, today_sent,
    )

    # 4. Telethon: connect and send
    client = TelegramClient("broadcast_session", cfg.api_id, cfg.api_hash)
    await client.start()
    me = await client.get_me()
    logger.info("Telethon client started as %s", me.first_name)

    sent = 0
    for idx, req in enumerate(batch):
        user = req["user"]
        user_id = user["id"]
        name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        username = user.get("username", "")

        logger.info("[%d/%d] Sending to %s (@%s, ID: %d)", idx + 1, len(batch), name, username, user_id)

        try:
            await client.send_message(user_id, build_dm_text(cfg.bot_username))
            append_log({
                "date": date.today().isoformat(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_id": user_id,
                "first_name": user.get("first_name"),
                "last_name": user.get("last_name"),
                "username": username,
                "status": "sent",
            })
            sent += 1
            logger.info("✅ DM sent to %s", name)
        except FloodWaitError as e:
            wait = e.seconds + 10
            logger.warning("⏳ FloodWait %ds — stopping for today.", wait)
            append_log({
                "date": date.today().isoformat(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_id": user_id,
                "first_name": user.get("first_name"),
                "last_name": user.get("last_name"),
                "username": username,
                "status": "flood_wait",
                "error": str(e),
            })
            break  # Stop for today
        except UserPrivacyRestrictedError:
            logger.warning("🔒 Privacy restricted — %s skipped.", name)
            append_log({
                "date": date.today().isoformat(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_id": user_id,
                "first_name": user.get("first_name"),
                "last_name": user.get("last_name"),
                "username": username,
                "status": "privacy_restricted",
            })
        except UserIsBlockedError:
            logger.warning("🚫 Blocked by %s — skipped.", name)
            append_log({
                "date": date.today().isoformat(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_id": user_id,
                "first_name": user.get("first_name"),
                "last_name": user.get("last_name"),
                "username": username,
                "status": "blocked",
            })
        except Exception as exc:
            logger.error("❌ Failed for %s: %s", name, exc)
            append_log({
                "date": date.today().isoformat(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_id": user_id,
                "first_name": user.get("first_name"),
                "last_name": user.get("last_name"),
                "username": username,
                "status": "failed",
                "error": str(exc),
            })

        if idx < len(batch) - 1:
            delay = random.uniform(MIN_DELAY, MAX_DELAY)
            await asyncio.sleep(delay)

    logger.info("📊 Broadcast done. Sent %d/%d DM(s) today.", sent, len(batch))
    await client.disconnect()


# ── Stats ─────────────────────────────────────────────────────────────────────


async def show_stats() -> None:
    cfg = Config()
    cfg.validate_broadcast()

    pending = await get_pending_requests(cfg.bot_token, cfg.group_id)
    log = load_log()
    today_log = today_entries(log)
    sent_today = len([e for e in today_log if e.get("status") == "sent"])
    total_sent = len([e for e in log if e.get("status") == "sent"])
    remaining_today = max(0, MAX_DM_PER_DAY - sent_today)

    # Pending not yet contacted
    sent_ids = {e["user_id"] for e in log if e.get("status") == "sent"}
    uncontacted = len([r for r in pending if r["user"]["id"] not in sent_ids])

    print(f"\n📊 Broadcast Stats")
    print(f"{'─' * 40}")
    print(f"Pending join requests:    {len(pending)}")
    print(f"Uncontacted users:        {uncontacted}")
    print(f"Sent today:               {sent_today}/{MAX_DM_PER_DAY}")
    print(f"Remaining today:          {remaining_today}")
    print(f"Total sent (all time):    {total_sent}")
    print(f"{'─' * 40}\n")


# ── Entry ─────────────────────────────────────────────────────────────────────


async def main() -> None:
    if "--stats" in sys.argv:
        await show_stats()
    elif "--reset-log" in sys.argv:
        LOG_FILE.unlink(missing_ok=True)
        logger.info("Broadcast log reset.")
    else:
        await broadcast()


if __name__ == "__main__":
    asyncio.run(main())

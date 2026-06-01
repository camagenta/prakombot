import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import aiosqlite

logger = logging.getLogger(__name__)

DB_PATH = "verifications.db"

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    nama TEXT NOT NULL,
    nip TEXT NOT NULL,
    instansi TEXT NOT NULL,
    jenjang TEXT NOT NULL,
    file_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_SQL)
        await db.commit()
    logger.info("Database initialized")


async def save_verification(
    user_id: int,
    nama: str,
    nip: str,
    instansi: str,
    jenjang: str,
    file_id: str,
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """INSERT INTO verifications
               (user_id, nama, nip, instansi, jenjang, file_id, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (user_id, nama, nip, instansi, jenjang, file_id, now, now),
        )
        await db.commit()
        return cur.lastrowid


async def get_verification(verif_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM verifications WHERE id = ?", (verif_id,)
        )
        row = await cur.fetchone()
        if row is None:
            return None
        return dict(row)


async def update_status(verif_id: int, status: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE verifications SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, verif_id),
        )
        await db.commit()


async def get_verification_by_user(user_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM verifications WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        )
        row = await cur.fetchone()
        if row is None:
            return None
        return dict(row)


if __name__ == "__main__":
    asyncio.run(init_db())
    logger.info("Database tables created successfully")

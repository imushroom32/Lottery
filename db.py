"""
Асинхронные функции работы с SQLite для лотереи.

Содержит:
- инициализацию схемы
- CRUD для билетов
- архивацию лотереи
"""

from __future__ import annotations
import os
from pathlib import Path

import aiosqlite
from typing import Any, Dict, List, Optional, Tuple


# Путь к базе: по умолчанию — файл рядом с проектом
DEFAULT_DB_PATH = (Path(__file__).parent / "data" / "lottery_db.sqlite").as_posix()
DB_PATH = os.getenv("DB_PATH", DEFAULT_DB_PATH)

# Гарантируем существование директории для БД (иначе sqlite выдаст unable to open database file)
db_dir = os.path.dirname(DB_PATH)
if db_dir:
    os.makedirs(db_dir, exist_ok=True)


CREATE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_number INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    username TEXT,
    file_id TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    comment TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS tickets_archive (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_number INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    username TEXT,
    file_id TEXT NOT NULL,
    status TEXT,
    comment TEXT,
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lotteries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMP
);
"""


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_SCHEMA_SQL)
        # Создаём запись о лотерее, если таблица пуста
        cursor = await db.execute("SELECT COUNT(1) FROM lotteries")
        row = await cursor.fetchone()
        if row and int(row[0]) == 0:
            await db.execute("INSERT INTO lotteries DEFAULT VALUES")
        await db.commit()


async def get_next_ticket_number() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COALESCE(MAX(ticket_number), 0) + 1 FROM tickets"
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else 1


async def add_ticket(ticket_number: int, user_id: int, username: Optional[str], file_id: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO tickets (ticket_number, user_id, username, file_id, status)
            VALUES (?, ?, ?, ?, 'active')
            """,
            (ticket_number, user_id, username, file_id),
        )
        await db.commit()
        return cursor.lastrowid


async def get_active_tickets_by_user(user_id: int) -> List[Tuple[int]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT ticket_number FROM tickets WHERE user_id = ? AND status = 'active' ORDER BY ticket_number",
            (user_id,),
        )
        return await cursor.fetchall()


async def get_active_ticket_by_number(ticket_number: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT id, ticket_number, user_id, username, file_id, status, comment
            FROM tickets WHERE ticket_number = ? AND status = 'active'
            """,
            (ticket_number,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        keys = [d[0] for d in cursor.description]
        return dict(zip(keys, row))


async def get_ticket_by_number_any_status(ticket_number: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT id, ticket_number, user_id, username, file_id, status, comment
            FROM tickets WHERE ticket_number = ?
            """,
            (ticket_number,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        keys = [d[0] for d in cursor.description]
        return dict(zip(keys, row))


async def set_ticket_status(ticket_number: int, status: str, comment: Optional[str]) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tickets SET status = ?, comment = ? WHERE ticket_number = ?",
            (status, comment, ticket_number),
        )
        await db.commit()


async def get_random_active_ticket() -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT id, ticket_number, user_id, username, file_id, status, comment
            FROM tickets
            WHERE status = 'active'
            ORDER BY RANDOM()
            LIMIT 1
            """
        )
        row = await cursor.fetchone()
        if not row:
            return None
        keys = [d[0] for d in cursor.description]
        return dict(zip(keys, row))


async def archive_lottery() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        # Копируем текущие билеты в архив
        await db.execute(
            """
            INSERT INTO tickets_archive (ticket_number, user_id, username, file_id, status, comment)
            SELECT ticket_number, user_id, username, file_id, status, comment FROM tickets
            """
        )
        # Очищаем активные билеты
        await db.execute("DELETE FROM tickets")
        # Закрываем текущую лотерею
        await db.execute(
            "UPDATE lotteries SET archived_at = CURRENT_TIMESTAMP WHERE archived_at IS NULL"
        )
        # Открываем новую
        await db.execute("INSERT INTO lotteries DEFAULT VALUES")
        await db.commit()



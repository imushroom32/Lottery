"""
Вспомогательные функции: проверки ролей, парсинг чисел, защита от параллельного розыгрыша.
"""

import asyncio
from typing import Iterable, Optional


class DrawLock:
    """Глобальная блокировка, чтобы исключить параллельный розыгрыш."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        await self._lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._lock.release()

    @property
    def locked(self) -> bool:
        return self._lock.locked()


draw_lock = DrawLock()


def is_admin(user_id: int, admin_ids: Iterable[int]) -> bool:
    return int(user_id) in set(int(x) for x in admin_ids)


def parse_int_safe(text: str) -> Optional[int]:
    try:
        return int(text)
    except (TypeError, ValueError):
        return None



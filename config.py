"""
Загрузка и валидация переменных окружения для бота.
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv, find_dotenv


@dataclass
class Settings:
    bot_token: str
    admin_ids: List[int]
    group_chat_id: int


def _parse_admin_ids(value: str) -> List[int]:
    if not value:
        return []
    result: List[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            result.append(int(part))
        except ValueError:
            raise ValueError("ADMIN_IDS должен быть списком чисел, разделённых запятыми")
    return result


def load_settings() -> Settings:
    # 1) Пытаемся найти .env, поднимаясь от текущей рабочей директории
    env_path = find_dotenv(usecwd=True)
    if env_path:
        load_dotenv(dotenv_path=env_path, override=True, encoding="utf-8")
    else:
        # 2) Пробуем .env рядом с текущим модулем (путь проекта при прямом запуске)
        module_env = Path(__file__).with_name(".env")
        if module_env.exists():
            load_dotenv(dotenv_path=module_env.as_posix(), override=True, encoding="utf-8")
        else:
            # 3) Последняя попытка — стандартный поиск в CWD
            load_dotenv(override=True, encoding="utf-8")

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("Не указан BOT_TOKEN в окружении")

    group_chat_id_raw = os.getenv("GROUP_CHAT_ID", "").strip()
    if not group_chat_id_raw:
        raise RuntimeError("Не указан GROUP_CHAT_ID в окружении")
    try:
        group_chat_id = int(group_chat_id_raw)
    except ValueError as exc:
        raise RuntimeError("GROUP_CHAT_ID должен быть числом") from exc

    admin_ids_raw = os.getenv("ADMIN_IDS", "").strip()
    admin_ids = _parse_admin_ids(admin_ids_raw)

    if not admin_ids:
        raise RuntimeError("Список ADMIN_IDS пуст. Укажите хотя бы одного администратора")

    return Settings(
        bot_token=bot_token,
        admin_ids=admin_ids,
        group_chat_id=group_chat_id,
    )



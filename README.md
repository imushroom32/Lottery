## Лотерейный Telegram-бот (aiogram + SQLite)

### Запуск локально
1. Установите зависимости:
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
2. Подготовьте переменные окружения:
```bash
export BOT_TOKEN="<Токен_бота>"
export GROUP_CHAT_ID="-1001234567890"
export ADMIN_IDS="12345,67890"
```
3. Запустите бота:
```bash
python bot.py
```

### Переменные окружения
- BOT_TOKEN — токен Telegram-бота
- GROUP_CHAT_ID — ID группы для публикаций
- ADMIN_IDS — список ID админов через запятую

### Стек
- aiogram 3
- SQLite (aiosqlite)
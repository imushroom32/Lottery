"""
Клавиатуры для пользователей и админов.
"""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton


def user_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📸 Загрузить новое фото")],
            [KeyboardButton(text="🎟 Посмотреть мои лотерейные билетики")],
            [KeyboardButton(text="🔍 Посмотреть фото по номеру билетика")],
            [KeyboardButton(text="⬅️ В меню")],
        ],
        resize_keyboard=True,
    )


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎲 Запустить розыгрыш")],
            [KeyboardButton(text="📷 Показать фото по номеру")],
            [KeyboardButton(text="🗑 Удалить билетик")],
            [KeyboardButton(text="📦 Архивировать лотерею")],
            [KeyboardButton(text="⬅️ В меню")],
        ],
        resize_keyboard=True,
    )


def back_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ В меню")]],
        resize_keyboard=True,
    )


def lottery_inline_actions(ticket_number: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить победителя", callback_data=f"confirm_win:{ticket_number}"),
                InlineKeyboardButton(text="❌ Отклонить билет", callback_data=f"reject_win:{ticket_number}"),
            ]
        ]
    )



"""
Клавиатуры для пользователей и админов.
"""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton


def user_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📸 Загрузить новое фото")],
            [KeyboardButton(text="🎟 Посмотреть мои лотерейные билетики")],
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


def user_tickets_inline_keyboard(ticket_numbers: list) -> InlineKeyboardMarkup:
    """Создает inline-клавиатуру с номерами билетов пользователя"""
    if not ticket_numbers:
        return InlineKeyboardMarkup(inline_keyboard=[])
    
    # Создаем кнопки по 2 в ряд для компактности
    keyboard = []
    for i in range(0, len(ticket_numbers), 2):
        row = []
        for j in range(2):
            if i + j < len(ticket_numbers):
                ticket_num = ticket_numbers[i + j]
                row.append(InlineKeyboardButton(
                    text=f"🎟 №{ticket_num}", 
                    callback_data=f"view_ticket:{ticket_num}"
                ))
        keyboard.append(row)
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)



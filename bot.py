"""
Основной бот на aiogram 3 с FSM и SQLite.
Запуск: python bot.py
"""

import asyncio
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ContentType
from aiogram.client.default import DefaultBotProperties

from config import load_settings
from db import (
    init_db,
    get_next_ticket_number,
    add_ticket,
    get_active_tickets_by_user,
    get_active_ticket_by_number,
    get_ticket_by_number_any_status,
    set_ticket_status,
    get_random_active_ticket,
    archive_lottery,
)
from keyboards import admin_menu, user_menu, back_menu, lottery_inline_actions, user_tickets_inline_keyboard
from utils import draw_lock, is_admin, parse_int_safe


class AskTicketNumber(StatesGroup):
    admin_view = State()
    admin_delete = State()


class AskReason(StatesGroup):
    reject_reason = State()
    delete_reason = State()


class UploadPhoto(StatesGroup):
    waiting_for_photo = State()


# Глобальная переменная для settings
_settings = None


def get_settings():
    return _settings


async def start_menu(message: Message) -> None:
    settings = get_settings()
    if is_admin(message.from_user.id, settings.admin_ids):
        await message.answer("Главное меню (админ)", reply_markup=admin_menu())
    else:
        await message.answer("Главное меню", reply_markup=user_menu())


async def on_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await start_menu(message)


async def start_photo_upload(message: Message, state: FSMContext) -> None:
    """Начало процесса загрузки фото"""
    await state.set_state(UploadPhoto.waiting_for_photo)
    await message.answer(
        "📸 <b>Загрузка фото для лотереи</b>\n\n"
        "Чтобы загрузить фото:\n"
        "1️⃣ Нажмите на кнопку <b>📎</b> (скрепка) в поле ввода сообщения\n"
        "2️⃣ Выберите <b>📷 Фото</b>\n"
        "3️⃣ Выберите фото из галереи или сделайте новое\n"
        "4️⃣ Отправьте фото\n\n"
        "💡 <i>Или просто перетащите фото в чат</i>\n\n"
        "❌ Для отмены нажмите кнопку '⬅️ В меню'",
        reply_markup=back_menu(),
        parse_mode="HTML"
    )


async def handle_upload_photo(message: Message, state: FSMContext) -> None:
    """Обработка загруженного фото"""
    settings = get_settings()
    
    # Проверяем, что мы в состоянии ожидания фото
    current_state = await state.get_state()
    if current_state != UploadPhoto.waiting_for_photo:
        return
    
    if not message.photo:
        await message.answer(
            "❌ Пожалуйста, отправьте именно <b>фото</b>, а не другой тип файла.\n\n"
            "Попробуйте снова или нажмите '⬅️ В меню' для отмены.",
            reply_markup=back_menu(),
            parse_mode="HTML"
        )
        return
    
    # Обрабатываем фото
    largest_photo = max(message.photo, key=lambda p: p.file_size or 0)
    file_id = largest_photo.file_id
    ticket_number = await get_next_ticket_number()
    await add_ticket(ticket_number, message.from_user.id, message.from_user.username, file_id)
    
    # Очищаем состояние
    await state.clear()
    
    # Отправляем подтверждение
    await message.answer(
        f"✅ <b>Отлично!</b> Ваш билет зарегистрирован!\n\n"
        f"🎟 <b>Номер билета: №{ticket_number}</b>\n\n"
        f"Теперь вы можете посмотреть свои билеты в главном меню.",
        reply_markup=user_menu(),
        parse_mode="HTML"
    )
    
    # Уведомляем в группу
    await message.bot.send_message(
        chat_id=settings.group_chat_id,
        text=f"🎟 Пользователь @{message.from_user.username or message.from_user.id} получил билет №{ticket_number}",
    )


async def handle_my_tickets(message: Message) -> None:
    rows = await get_active_tickets_by_user(message.from_user.id)
    if not rows:
        await message.answer("У вас нет активных билетов")
        return
    
    # Извлекаем номера билетов из кортежей
    ticket_numbers = [row[0] for row in rows]
    
    # Создаем inline-клавиатуру с номерами билетов
    keyboard = user_tickets_inline_keyboard(ticket_numbers)
    
    await message.answer(
        f"🎟 Ваши активные билеты ({len(ticket_numbers)} шт.):\n\nНажмите на номер билета, чтобы посмотреть фото:",
        reply_markup=keyboard
    )




async def admin_start_draw(message: Message) -> None:
    settings = get_settings()
    if not is_admin(message.from_user.id, settings.admin_ids):
        await message.answer("Недостаточно прав")
        return
    if draw_lock.locked:
        await message.answer("⏳ Розыгрыш уже идёт, дождитесь завершения")
        return
    async with draw_lock:
        ticket = await get_random_active_ticket()
        if not ticket:
            await message.answer("⚠️ Нет активных билетов для розыгрыша")
            return
        await message.answer_photo(
            ticket["file_id"],
            caption=f"🎲 Выпал билет №{ticket['ticket_number']} (@{ticket['username']})",
            reply_markup=lottery_inline_actions(ticket["ticket_number"]),
        )


async def admin_confirm_winner(callback: CallbackQuery) -> None:
    settings = get_settings()
    if not is_admin(callback.from_user.id, settings.admin_ids):
        await callback.answer("Нет прав", show_alert=True)
        return
    if not callback.data or not callback.data.startswith("confirm_win:"):
        return
    num = parse_int_safe(callback.data.split(":", 1)[1])
    if num is None:
        await callback.answer("Некорректный номер", show_alert=True)
        return
    ticket = await get_ticket_by_number_any_status(num)
    if not ticket or ticket["status"] != "active":
        await callback.answer("Билет недоступен", show_alert=True)
        return
    await set_ticket_status(num, "rejected", None)  # чтобы победитель больше не участвовал
    await callback.message.bot.send_message(
        settings.group_chat_id,
        f"🏆 Победитель: билет №{num} (@{ticket['username']})!",
    )
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Победитель опубликован")


async def admin_reject_ticket_start(callback: CallbackQuery, state: FSMContext) -> None:
    settings = get_settings()
    if not is_admin(callback.from_user.id, settings.admin_ids):
        await callback.answer("Нет прав", show_alert=True)
        return
    if not callback.data or not callback.data.startswith("reject_win:"):
        return
    num = parse_int_safe(callback.data.split(":", 1)[1])
    if num is None:
        await callback.answer("Некорректный номер", show_alert=True)
        return
    await state.set_state(AskReason.reject_reason)
    await state.update_data(ticket_number=num)
    await callback.message.answer("Укажите причину отклонения", reply_markup=back_menu())
    await callback.answer()


async def admin_reject_reason_input(message: Message, state: FSMContext) -> None:
    settings = get_settings()
    if message.text == "⬅️ В меню":
        await state.clear()
        await start_menu(message)
        return
    reason = message.text.strip()
    data = await state.get_data()
    num = data.get("ticket_number")
    await set_ticket_status(int(num), "rejected", reason)
    await message.bot.send_message(
        settings.group_chat_id,
        f"🚫 Билет №{num} отклонён. Причина: {reason}",
    )
    await state.clear()
    # Автозапуск нового розыгрыша
    await admin_start_draw(message)


async def admin_show_by_number_ask(message: Message, state: FSMContext) -> None:
    await state.set_state(AskTicketNumber.admin_view)
    await message.answer("Введите номер билета", reply_markup=back_menu())


async def admin_show_by_number_input(message: Message, state: FSMContext) -> None:
    if message.text == "⬅️ В меню":
        await state.clear()
        await start_menu(message)
        return
    num = parse_int_safe(message.text)
    if num is None:
        await message.answer("Введите число")
        return
    ticket = await get_ticket_by_number_any_status(num)
    if not ticket:
        await message.answer("❌ Билет не найден")
        return
    await message.answer_photo(ticket["file_id"], caption=f"Билет №{ticket['ticket_number']} (@{ticket['username']}) | статус: {ticket['status']}")
    await state.clear()


async def admin_delete_ask(message: Message, state: FSMContext) -> None:
    await state.set_state(AskTicketNumber.admin_delete)
    await message.answer("Введите номер билета для удаления", reply_markup=back_menu())


async def admin_delete_number_input(message: Message, state: FSMContext) -> None:
    if message.text == "⬅️ В меню":
        await state.clear()
        return
    num = parse_int_safe(message.text)
    if num is None:
        await message.answer("Введите число")
        return
    await state.update_data(ticket_number=num)
    await state.set_state(AskReason.delete_reason)
    await message.answer("Укажите причину удаления", reply_markup=back_menu())


async def admin_delete_reason_input(message: Message, state: FSMContext) -> None:
    settings = get_settings()
    if message.text == "⬅️ В меню":
        await state.clear()
        await start_menu(message)
        return
    reason = message.text.strip()
    data = await state.get_data()
    num = int(data.get("ticket_number"))
    await set_ticket_status(num, "deleted", reason)
    await message.bot.send_message(
        settings.group_chat_id,
        f"🗑 Билет №{num} удалён. Причина: {reason}",
    )
    await state.clear()


async def user_view_ticket_callback(callback: CallbackQuery) -> None:
    """Обработчик нажатия на кнопку с номером билета"""
    if not callback.data or not callback.data.startswith("view_ticket:"):
        await callback.answer("Некорректный запрос", show_alert=True)
        return
    
    # Извлекаем номер билета из callback_data
    num = parse_int_safe(callback.data.split(":", 1)[1])
    if num is None:
        await callback.answer("Некорректный номер билета", show_alert=True)
        return
    
    # Получаем билет
    ticket = await get_active_ticket_by_number(num)
    if not ticket:
        await callback.answer("❌ Билет не найден или архивирован", show_alert=True)
        return
    
    # Проверяем, что билет принадлежит пользователю
    if ticket["user_id"] != callback.from_user.id:
        await callback.answer("❌ У вас нет доступа к этому билету", show_alert=True)
        return
    
    # Отправляем фото
    await callback.message.answer_photo(
        ticket["file_id"], 
        caption=f"🎟 Ваш билет №{ticket['ticket_number']}"
    )
    await callback.answer()


async def admin_archive(message: Message) -> None:
    settings = get_settings()
    await archive_lottery()
    await message.bot.send_message(
        settings.group_chat_id,
        "📦 Лотерея завершена, все записи архивированы",
    )


async def main() -> None:
    global _settings
    _settings = load_settings()
    await init_db()

    bot = Bot(
        token=_settings.bot_token,
        default=DefaultBotProperties(parse_mode="HTML")
    )
    dp = Dispatcher()

    # Команды и меню
    dp.message.register(on_start, CommandStart())

    # Пользовательские действия
    dp.message.register(start_photo_upload, F.text == "📸 Загрузить новое фото")
    dp.message.register(handle_upload_photo, F.photo, UploadPhoto.waiting_for_photo)
    dp.message.register(handle_my_tickets, F.text == "🎟 Посмотреть мои лотерейные билетики")

    # Админские действия
    dp.message.register(admin_start_draw, F.text == "🎲 Запустить розыгрыш")
    dp.message.register(admin_show_by_number_ask, F.text == "📷 Показать фото по номеру")
    dp.message.register(admin_show_by_number_input, AskTicketNumber.admin_view)

    dp.callback_query.register(admin_confirm_winner, F.data.startswith("confirm_win:"))
    dp.callback_query.register(admin_reject_ticket_start, F.data.startswith("reject_win:"))
    dp.callback_query.register(user_view_ticket_callback, F.data.startswith("view_ticket:"))
    dp.message.register(admin_reject_reason_input, AskReason.reject_reason)

    dp.message.register(admin_delete_ask, F.text == "🗑 Удалить билетик")
    dp.message.register(admin_delete_number_input, AskTicketNumber.admin_delete)
    dp.message.register(admin_delete_reason_input, AskReason.delete_reason)

    dp.message.register(start_menu, F.text == "⬅️ В меню")
    
    # Обработка отмены загрузки фото
    dp.message.register(start_menu, F.text == "⬅️ В меню", UploadPhoto.waiting_for_photo)
    
    # Обработка неправильного типа файла во время ожидания фото
    async def handle_wrong_file_type(message: Message, state: FSMContext) -> None:
        await message.answer(
            "❌ Пожалуйста, отправьте именно <b>фото</b>, а не другой тип файла.\n\n"
            "Попробуйте снова или нажмите '⬅️ В меню' для отмены.",
            reply_markup=back_menu(),
            parse_mode="HTML"
        )
    
    dp.message.register(handle_wrong_file_type, UploadPhoto.waiting_for_photo)

    # Архивирование
    dp.message.register(admin_archive, F.text == "📦 Архивировать лотерею")

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
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
from keyboards import admin_menu, user_menu, back_menu, lottery_inline_actions
from utils import draw_lock, is_admin, parse_int_safe


class AskTicketNumber(StatesGroup):
    user_view = State()
    admin_view = State()
    admin_delete = State()


class AskReason(StatesGroup):
    reject_reason = State()
    delete_reason = State()


async def start_menu(message: Message, settings) -> None:
    if is_admin(message.from_user.id, settings.admin_ids):
        await message.answer("Главное меню (админ)", reply_markup=admin_menu())
    else:
        await message.answer("Главное меню", reply_markup=user_menu())


async def on_start(message: Message, state: FSMContext, settings) -> None:
    await state.clear()
    await start_menu(message, settings)


async def handle_upload_photo(message: Message, settings) -> None:
    if not message.photo:
        await message.answer("Пожалуйста, отправьте фото")
        return
    largest_photo = max(message.photo, key=lambda p: p.file_size or 0)
    file_id = largest_photo.file_id
    ticket_number = await get_next_ticket_number()
    await add_ticket(ticket_number, message.from_user.id, message.from_user.username, file_id)
    await message.answer(f"✅ Ваш билет зарегистрирован! Номер: №{ticket_number}")
    await message.bot.send_message(
        chat_id=settings.group_chat_id,
        text=f"🎟 Пользователь @{message.from_user.username or message.from_user.id} получил билет №{ticket_number}",
    )


async def handle_my_tickets(message: Message) -> None:
    rows = await get_active_tickets_by_user(message.from_user.id)
    if not rows:
        await message.answer("У вас нет активных билетов")
        return
    numbers = ", ".join(f"№{r[0]}" for r in rows)
    await message.answer(f"Ваши активные билеты: {numbers}")


async def ask_user_ticket_number(message: Message, state: FSMContext) -> None:
    await state.set_state(AskTicketNumber.user_view)
    await message.answer("Введите номер билета", reply_markup=back_menu())


async def user_send_ticket_number(message: Message, state: FSMContext) -> None:
    if message.text == "⬅️ В меню":
        await state.clear()
        await message.answer("Главное меню", reply_markup=user_menu())
        return
    num = parse_int_safe(message.text)
    if num is None:
        await message.answer("Введите число")
        return
    ticket = await get_active_ticket_by_number(num)
    if not ticket:
        await message.answer("❌ Билет с таким номером не найден или он архивирован")
        return
    await message.answer_photo(ticket["file_id"], caption=f"Билет №{ticket['ticket_number']} (@{ticket['username']})")
    await state.clear()


async def admin_start_draw(message: Message, settings) -> None:
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


async def admin_confirm_winner(callback: CallbackQuery, settings) -> None:
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


async def admin_reject_ticket_start(callback: CallbackQuery, state: FSMContext, settings) -> None:
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


async def admin_reject_reason_input(message: Message, state: FSMContext, settings) -> None:
    if message.text == "⬅️ В меню":
        await state.clear()
        await start_menu(message, settings)
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
    await admin_start_draw(message, settings)


async def admin_show_by_number_ask(message: Message, state: FSMContext) -> None:
    await state.set_state(AskTicketNumber.admin_view)
    await message.answer("Введите номер билета", reply_markup=back_menu())


async def admin_show_by_number_input(message: Message, state: FSMContext, settings) -> None:
    if message.text == "⬅️ В меню":
        await state.clear()
        await start_menu(message, settings)
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


async def admin_delete_reason_input(message: Message, state: FSMContext, settings) -> None:
    if message.text == "⬅️ В меню":
        await state.clear()
        await start_menu(message, settings)
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


async def admin_archive(message: Message, settings) -> None:
    await archive_lottery()
    await message.bot.send_message(
        settings.group_chat_id,
        "📦 Лотерея завершена, все записи архивированы",
    )


async def main() -> None:
    settings = load_settings()
    await init_db()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode="HTML")
    )
    dp = Dispatcher()

    # Команды и меню
    dp.message.register(lambda m: on_start(m, dp.fsm.get_context(m.chat.id, m.from_user.id), settings), CommandStart())

    # Пользовательские действия
    dp.message.register(lambda m: handle_upload_photo(m, settings), F.photo)
    dp.message.register(lambda m: handle_my_tickets(m), F.text == "🎟 Посмотреть мои лотерейные билетики")
    dp.message.register(ask_user_ticket_number, F.text == "🔍 Посмотреть фото по номеру билетика")
    dp.message.register(user_send_ticket_number, AskTicketNumber.user_view)

    # Админские действия
    dp.message.register(lambda m: admin_start_draw(m, settings), F.text == "🎲 Запустить розыгрыш")
    dp.message.register(admin_show_by_number_ask, F.text == "📷 Показать фото по номеру")
    dp.message.register(lambda m, s=dp.fsm: admin_show_by_number_input(m, s.get_context(m.chat.id, m.from_user.id), settings), AskTicketNumber.admin_view)

    dp.callback_query.register(lambda c: admin_confirm_winner(c, settings), F.data.startswith("confirm_win:"))
    dp.callback_query.register(lambda c, s=dp.fsm: admin_reject_ticket_start(c, s.get_context(c.message.chat.id, c.from_user.id), settings), F.data.startswith("reject_win:"))
    dp.message.register(lambda m, s=dp.fsm: admin_reject_reason_input(m, s.get_context(m.chat.id, m.from_user.id), settings), AskReason.reject_reason)

    dp.message.register(admin_delete_ask, F.text == "🗑 Удалить билетик")
    dp.message.register(admin_delete_number_input, AskTicketNumber.admin_delete)
    dp.message.register(lambda m, s=dp.fsm: admin_delete_reason_input(m, s.get_context(m.chat.id, m.from_user.id), settings), AskReason.delete_reason)

    dp.message.register(lambda m: start_menu(m, settings), F.text == "⬅️ В меню")

    # Архивирование
    dp.message.register(lambda m: admin_archive(m, settings), F.text == "📦 Архивировать лотерею")

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())



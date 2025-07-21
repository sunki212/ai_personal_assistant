import re
from aiogram import Router, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from lists_of_users.create_JSON_lists import load_admitted, save_applications


application_router = Router()

class Form_application(StatesGroup):
    fio = State()
    tg_username = State()

@application_router.callback_query(F.data == "leave_request")
async def leave_request(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer("Введите Ваши Ф.И.О. чтобы представиться Владимиру Викторовичу")
    await state.set_state(Form_application.fio)
    await state.update_data(message_to_delete=callback.message.message_id)

@application_router.callback_query(F.data == "cancel_request")
async def cancel_request(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await state.clear()

@application_router.message(Form_application.fio)
async def process_fio(message: Message, state: FSMContext):
    await state.update_data(fio=message.text)
    await message.answer("Напишите Ваш телеграмм username. Например @example")
    await state.set_state(Form_application.tg_username)

@application_router.message(Form_application.tg_username)
async def process_username(message: Message, state: FSMContext):
    username = message.text.strip()
    
    if not re.match(r'^@[a-zA-Z0-9_]{5,32}$', username):
        await message.answer("❌ Некорректный username. Формат: @example")
        return

    data = await state.get_data()
    fio = data.get("fio", "")
    
    if not fio:
        await message.answer("❌ Ошибка: ФИО не найдено")
        return

    # Обновляем словарь и сохраняем в JSON
    list_of_users = load_admitted()
    list_of_users[username] = fio
    save_applications(list_of_users)  # сохраняем изменения
    
    await message.answer("✅ Заявка сохранена!")
    await state.clear()
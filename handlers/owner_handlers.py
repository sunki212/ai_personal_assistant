from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import owners
from lists_of_users.create_JSON_lists import load_applications, load_admitted, load_blacklist, save_admitted, save_applications, save_blacklist
from handlers.handlers import Form_with_AI
from keyboards import owners_keyboard, admitted_keyboard

owners_router = Router()


class OwnerStates(StatesGroup):
    VIEW_APPLICATIONS = State()
    VIEW_ADMITTED = State()
    VIEW_BLACKLIST = State()
    PROCESS_APPLICATION = State()
    PROCESS_PERMISSION = State()
    PROCESS_BLACKLIST = State()

# Обработчики для Reply-клавиатуры
@owners_router.message(lambda message: message.text == "📋 Заявки")
async def handle_view_applications(message: Message, state: FSMContext):
    """Обработчик кнопки 'Просмотр заявок'"""
    await view_applications(message, state)

@owners_router.message(lambda message: message.text == "✅ Разрешённые")
async def handle_view_admitted(message: Message, state: FSMContext):
    """Обработчик кнопки 'Просмотр разрешённых пользователей'"""
    await view_admitted(message, state)

@owners_router.message(lambda message: message.text == "🚫 Чёрный список")
async def handle_view_blacklist(message: Message, state: FSMContext):
    """Обработчик кнопки 'Просмотр чёрного списка'"""
    await view_blacklist(message, state)

# Функции для обработки
async def view_applications(message: types.Message, state: FSMContext):
    """Показывает заявки на доступ"""
    applications = load_applications()
    if not applications:
        await message.answer("Нет новых заявок.")
        return
    
    buttons = [
        [InlineKeyboardButton(text=username, callback_data=f"app_{user_id}")]
        for user_id, username in applications.items()
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await message.answer(
        "Нажмите по соответствующей клавише, чтобы принять решение о доступе:",
        reply_markup=keyboard
    )
    await state.set_state(OwnerStates.VIEW_APPLICATIONS)

async def view_admitted(message: types.Message, state: FSMContext):
    """Показывает список разрешенных пользователей"""
    admitted = load_admitted()
    if not admitted:
        await message.answer("Нет пользователей с доступом.")
        return
    
    buttons = [
        [InlineKeyboardButton(text=username, callback_data=f"perm_{user_id}")]
        for user_id, username in admitted.items()
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await message.answer(
        "Нажмите по соответствующей клавише для управления доступом:",
        reply_markup=keyboard
    )
    await state.set_state(OwnerStates.VIEW_ADMITTED)

async def view_blacklist(message: types.Message, state: FSMContext):
    """Показывает чёрный список"""
    blacklist = load_blacklist()
    if not blacklist:
        await message.answer("Чёрный список пуст.")
        return
    
    buttons = [
        [InlineKeyboardButton(text=username, callback_data=f"bl_{user_id}")]
        for user_id, username in blacklist.items()
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await message.answer(
        "Нажмите по соответствующей клавише для управления доступом:",
        reply_markup=keyboard
    )
    await state.set_state(OwnerStates.VIEW_BLACKLIST)


async def is_owner(callback_or_message: types.Message | types.CallbackQuery) -> bool:
    """Проверка, является ли пользователь владельцем"""
    if isinstance(callback_or_message, types.CallbackQuery):
        user_id = callback_or_message.from_user.id  # Получаем ID из callback
    else:
        user_id = callback_or_message.from_user.id  # Получаем ID из сообщения
    
    print(f"Checking owner: {user_id} in {owners}")  # Отладочная информация
    return user_id in owners


# Обработчик inline-кнопок
@owners_router.callback_query()
async def handle_inline_buttons(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Полный обработчик inline кнопок для работы с форматом {@username: "Фамилия И.О."}"""
    try:
        # Проверка прав владельца
        if not await is_owner(callback):
            await callback.answer("⚠️ Только для владельцев бота", show_alert=True)
            return

        data = callback.data
        applications = load_applications()
        admitted = load_admitted()
        blacklist = load_blacklist()

        # Обработка заявок (VIEW_APPLICATIONS)
        if data.startswith("app_"):
            username = data[4:]  # Получаем username из callback данных
            
            if username in applications:
                full_name = applications[username]
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{username}"),
                        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{username}")
                    ]
                ])
                
                await callback.message.edit_text(
                    f"Заявка от {full_name} ({username})\n\nВыберите действие:",
                    reply_markup=keyboard
                )
                await state.set_state(OwnerStates.PROCESS_APPLICATION)
            else:
                await callback.answer("❌ Заявка не найдена", show_alert=True)

        # Одобрение заявки (PROCESS_APPLICATION)
        elif data.startswith("approve_"):
            username = data[8:]
            
            if username in applications:
                full_name = applications[username]
                admitted[username] = full_name
                del applications[username]
                
                save_admitted(admitted)
                save_applications(applications)
                
                await callback.message.edit_text(
                    f"✅ Доступ предоставлен: {full_name} ({username})"
                )
                
                # Попытка уведомить пользователя
                try:
                    await bot.send_message(
                        chat_id=username,
                        text=f"🎉 Ваша заявка одобрена, {full_name}! Теперь вы можете пользоваться ботом."
                    )
                except Exception as e:
                    print(f"Не удалось уведомить пользователя: {e}")
                
            else:
                await callback.answer("❌ Заявка не найдена", show_alert=True)
            
            await state.clear()

        # Отклонение заявки (PROCESS_APPLICATION)
        elif data.startswith("reject_"):
            username = data[7:]
            
            if username in applications:
                full_name = applications[username]
                del applications[username]
                save_applications(applications)
                
                await callback.message.edit_text(
                    f"❌ Заявка отклонена: {full_name} ({username})"
                )
            else:
                await callback.answer("❌ Заявка не найдена", show_alert=True)
            
            await state.clear()

        # Просмотр разрешенных пользователей (VIEW_ADMITTED)
        elif data.startswith("perm_"):
            username = data[5:]
            
            if username in admitted:
                full_name = admitted[username]
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🚫 Забанить", callback_data=f"revoke_{username}"),
                        InlineKeyboardButton(text="🔙 Назад", callback_data="cancel")
                    ]
                ])
                
                await callback.message.edit_text(
                    f"Пользователь: {full_name} ({username})\n\nУбрать доступ?",
                    reply_markup=keyboard
                )
                await state.set_state(OwnerStates.PROCESS_PERMISSION)
            else:
                await callback.answer("❌ Пользователь не найден", show_alert=True)

        # Прекращение доступа (PROCESS_PERMISSION)
        elif data.startswith("revoke_"):
            username = data[7:]
            
            if username in admitted:
                full_name = admitted[username]
                blacklist[username] = full_name
                del admitted[username]
                
                save_admitted(admitted)
                save_blacklist(blacklist)
                
                await callback.message.edit_text(
                    f"🚫 Пользователь заблокирован: {full_name} ({username})"
                )
            else:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
            
            await state.clear()

        # Просмотр черного списка (VIEW_BLACKLIST)
        elif data.startswith("bl_"):
            username = data[3:]
            
            if username in blacklist:
                full_name = blacklist[username]
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Разбанить", callback_data=f"unban_{username}"),
                        InlineKeyboardButton(text="🔙 Назад", callback_data="cancel")
                    ]
                ])
                
                await callback.message.edit_text(
                    f"Заблокированный: {full_name} ({username})\n\nРазрешить доступ?",
                    reply_markup=keyboard
                )
                await state.set_state(OwnerStates.PROCESS_BLACKLIST)
            else:
                await callback.answer("❌ Пользователь не найден", show_alert=True)

        # Разблокировка (PROCESS_BLACKLIST)
        elif data.startswith("unban_"):
            username = data[6:]
            
            if username in blacklist:
                full_name = blacklist[username]
                admitted[username] = full_name
                del blacklist[username]
                
                save_blacklist(blacklist)
                save_admitted(admitted)
                
                await callback.message.edit_text(
                    f"✅ Пользователь разблокирован: {full_name} ({username})"
                )
            else:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
            
            await state.clear()

        # Отмена действия
        elif data == "cancel":
            await callback.message.delete()
            await state.clear()

        await callback.answer()

    except Exception as e:
        print(f"Ошибка в обработчике кнопок: {e}")
        await callback.answer("⚠️ Произошла ошибка при обработке", show_alert=True)
        
@owners_router.message(F.text == "💬 Общаться с ботом")
async def handle_chat_with_bot(message: types.Message, state: FSMContext):
    """
    Рабочий обработчик кнопки "Общаться с ботом" для владельцев
    """
    # Проверяем, является ли пользователь владельцем
    if f'@{message.from_user.username}' not in load_admitted():
        print(load_admitted(), message.from_user.username)
        await message.answer(
            "⚠️ Эта функция Вам не доступна",
            reply_markup=admitted_keyboard  # Возвращаем клавиатуру
        )
        return
    else:
        # Устанавливаем состояние для общения с ИИ
        await message.answer(
            "Режим общения с ботом активирован. Вы можете начать диалог.\n\n"
            'Для выхода введите "!!!выход!!!" или "/exit"',
            reply_markup=ReplyKeyboardRemove()  # Убираем клавиатуру
        )
        await state.set_state(Form_with_AI.default_communication)


# Дополнительно: обработчик для проверки состояния
@owners_router.message(Command("check_state"))
async def check_state(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    await message.answer(f"Текущее состояние: {current_state}")

async def handle_owner_commands(message: types.Message, state: FSMContext):
    """Обработчик команд хозяина"""
    if not await is_owner(message):
        return
    
    
def register_owner_handlers(dp: Dispatcher):
    """Регистрация обработчиков для хозяина"""
    dp.message.register(handle_owner_commands, lambda m: m.text in [
        "📋 Просмотр заявок", 
        "✅ Разрешённые", 
        "🚫 Чёрный список"
    ])
    dp.callback_query.register(handle_inline_buttons)
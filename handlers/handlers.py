import json
import re

from aiogram import Router, F, Bot, types, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from typing import Dict
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMIN_GROUP_ID, owners, developers
from lists_of_users.create_JSON_lists import load_admitted, load_blacklist, load_applications
from models import UserData
from generate import ai_generate, clear_context
from keyboards import application_key, owners_keyboard, admitted_keyboard
from db_operations.db_operatins import get_sessionmaker, get_message_contexts
from db_operations.process_messages import embedding_single_message, process_single_message
from Database.db_create import find_similar_messages

applications: Dict[str, str] = load_applications()
blacklist: Dict[str, str] = load_blacklist()
admitted: Dict[str, str] = load_admitted()

handlers_router = Router()
  
class Form_with_AI(StatesGroup):
    default_communication = State()
    
class Form_application(StatesGroup):
    fio = State()
    tg_username = State()
    
class DeveloperStates(StatesGroup):
    waiting_for_new_prompt = State()

@handlers_router.message(F.chat.id == ADMIN_GROUP_ID, F.text)
async def handle_admin_group_message(message: types.Message):
    """
    Обработка сообщений из админ-группы.
    Ожидаемый формат сообщения: __%название_промта%__\nтекст
    """
    text = message.text  # текст входящего сообщения

    # Регулярное выражение для проверки шаблона "__%название%__\nтекст"
    pattern = re.compile(r'^__%(.+?)%__\r?\n(.+)', re.DOTALL)
    match = pattern.match(text)

    if not match:
        # Если формат не соответствует, отправляем сообщение об ошибке
        await message.reply(
            "Неверный формат сообщения. Используйте: __%название_промта%__\\nтекст",
            quote=True
        )
        return

    # Извлекаем название промта и текст из сообщения
    prompt_name = match.group(1).strip()
    prompt_text = match.group(2).strip()

    # Загружаем существующие промты из JSON-файла (или создаем пустой словарь)
    try:
        with open("prompts.json", "r", encoding="utf-8") as file:
            prompts = json.load(file)
    except FileNotFoundError:
        prompts = {}

    # Сохраняем или обновляем промт в словаре
    prompts[prompt_name] = prompt_text

    # Записываем обновленный словарь обратно в JSON-файл
    with open("prompts.json", "w", encoding="utf-8") as file:
        json.dump(prompts, file, ensure_ascii=False, indent=4)

    # Подтверждаем сохранение промта
    await message.reply(f"Промт \"{prompt_name}\" сохранен/обновлен.", quote=True)

    

@handlers_router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    username = message.from_user.username
    # Загружаем актуальный список пользователей из JSON
    list_of_users = load_admitted()
    if message.from_user.id in owners:
        await message.answer(
            "Вы владелец бота",  # Текст сообщения
            reply_markup=owners_keyboard  # Клавиатура передается отдельно
        )
        return
    
    if f"@{username}" in admitted or len(list_of_users) is None:
        await message.answer(
            "✨ Добро пожаловать в чат с ботом Володей! ✨\n\n"
            "🤖 Бот Володя — ваш персональный собеседник, который:\n"
            "🔹 Ответит на вопросы, одобренные самим Владимиром Викторовичем и сохранённые в моей базе данных.\n"
            "🔹 Поддержит беседу так, будто вы общаетесь лично с Владимиром Викторовичем.\n\n"
            "💬 Просто напишите мне — и начнём! 🚀\n\n"
            "**P.S. Если хотите, можете даже представить, что это он сам вам отвечает — наш маленький секрет!** 😉",
            reply_markup=admitted_keyboard)
    else:
        await message.answer(
            "У вас нет доступа к боту, но вы можете оставить заявку.",
            reply_markup=application_key
        )
    

@handlers_router.message(Command("replace_prom"))
async def replace_prompt_start(message: types.Message, state: FSMContext):
    """Обработчик команды замены промта"""
    if message.from_user.id not in developers:
        await message.answer("⛔ Доступ только для разработчиков")
        return
    
    try:
        # Читаем текущий промт
        with open('promts.json', 'r', encoding='utf-8') as f:
            prompts = json.load(f)
        current_prompt = prompts.get('The_main_promt', 'Промт не найден')
        
        # Клавиатура с отменой
        cancel_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_prompt_update")]
            ]
        )
        
        # Отправляем сообщение с промтом
        sent_msg = await message.answer(
            f"Действующий промт:\n\n{current_prompt}\n\n"
            "Введите текст нового промта...",
            reply_markup=cancel_kb
        )
        
        # Сохраняем ID сообщения для последующего удаления
        await state.update_data(message_id=sent_msg.message_id)
        await state.set_state(DeveloperStates.waiting_for_new_prompt)
        
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {str(e)}")
        await state.clear()

@handlers_router.callback_query(F.data == "cancel_prompt_update")
async def cancel_prompt_update(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик отмены обновления промта"""
    data = await state.get_data()
    message_id = data.get('message_id')
    
    try:
        if message_id:
            await callback.bot.delete_message(
                chat_id=callback.message.chat.id,
                message_id=message_id
            )
    finally:
        await state.clear()
        await callback.answer("Обновление промта отменено")

@handlers_router.message(DeveloperStates.waiting_for_new_prompt)
async def process_new_prompt(message: types.Message, state: FSMContext):
    """Обработчик нового промта"""
    try:
        data = await state.get_data()
        message_id = data.get('message_id')
        
        # Обновляем файл
        with open('promts.json', 'r+', encoding='utf-8') as f:
            prompts = json.load(f)
            prompts['The_main_promt'] = message.text
            f.seek(0)
            json.dump(prompts, f, ensure_ascii=False, indent=4)
            f.truncate()
        
        # Удаляем служебное сообщение
        if message_id:
            try:
                await message.bot.delete_message(
                    chat_id=message.chat.id,
                    message_id=message_id
                )
            except Exception as e:
                print(f"Ошибка удаления: {e}")
        
        await message.answer("✅ Промт успешно обновлён")
        
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {str(e)}")
    finally:
        await state.clear()

@handlers_router.message(DeveloperStates.waiting_for_new_prompt)
async def process_new_prompt(message: types.Message, state: FSMContext):
    """Обработчик нового промта от разработчика"""
    try:
        # Обновляем промт в файле
        with open('promts.json', 'r+', encoding='utf-8') as f:
            data = json.load(f)
            data['The_main_promt'] = message.text
            f.seek(0)
            json.dump(data, f, ensure_ascii=False, indent=4)
            f.truncate()
        
        await message.answer("✅ Промт успешно обновлён")
        
    except Exception as e:
        await message.answer(f"⚠️ Ошибка при обновлении: {str(e)}")
    finally:
        await state.clear()
        
    
# Далее идёт общение с помощью AI
    
@handlers_router.message(Form_with_AI.default_communication)
async def process_default_communication(
    message: Message, 
    state: FSMContext, 
    bot: Bot,
    dispatcher: Dispatcher  # Добавляем Dispatcher в параметры
):
    # Проверка команды выхода в первую очередь
    if message.text and message.text.lower() in ("!!!выход!!!", "/exit"):
        await state.clear()
        if message.from_user.username in load_admitted():
            await message.answer(
            "✅ Режим общения с ИИ деактивирован",
            reply_markup=admitted_keyboard)
        elif message.from_user.id in owners:
            await message.answer(
            "✅ Режим общения с ИИ деактивирован",
            reply_markup=owners_keyboard)
        print(f"Пользователь {message.from_user.id} вышел из режима ИИ")
        return
    
    # Получаем данные из состояния
    data = await state.get_data()
    
    # Создаем объект UserData
    user_data = UserData(
        user_id=message.from_user.id,
        username=message.from_user.username,
        default_communication=data.get('default_communication', '')
    )
    
    # Получаем sessionmaker из dispatcher
    session_maker = await get_sessionmaker(dispatcher)
    
    # Генерируем ответ с помощью AI
    response = await ai_generate(
        user_id=message.from_user.id,
        username=message.from_user.username,
        text=message.text,
        bot=bot,
        user_data=user_data,
        promt_type="The_main_promt",
        session_maker=session_maker
    )
    print(f"{message.text}\n\n {response}")
    if re.findall(r"\|.+\|", response):
    # Создаем сессию через session_maker
        async with session_maker() as session:
            embed_response = await embedding_single_message(await process_single_message(str(re.findall(r"(?<=\|).+(?=\|)",response)[0]).strip("|")))
            message_tuples = await find_similar_messages(
                session=session,  # Передаем реальную сессию
                embedding=embed_response,
                threshold=0.1
            )
            context = await get_message_contexts(
                message_tuples=message_tuples,
                session=session  # Тоже передаем сессию
            )
            print(f' Результаты косинусного поиска \n{message_tuples} \n\nКонтекст:\n  {context}')
            
        response = await ai_generate(
            user_id=message.from_user.id,
            username=message.from_user.username,
            text=f'Пополнение контекста:Найди ответ на вопрос пользователя среди следующих сообщений:\n{context}\n\nЕсли ответа, ответь что у тебя нет информации/нет ответа, но в том же стиле как это ответил бы Владимир Викторович',
            bot=bot,
            user_data=user_data,
            promt_type="The_main_promt",
            session_maker=session_maker
        )
        
    # Отправляем ответ пользователю
    await message.answer(response)

    
@handlers_router.message(Command("reset"))
async def cmd_reset(message: Message, state: FSMContext):
    clear_context(message.from_user.id)
    await message.answer("Контекст диалога сброшен. Начнем заново!")
    await state.set_state(Form_with_AI.default_communication)
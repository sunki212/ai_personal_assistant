import os
import re
import json
from datetime import time, date
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import func
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram import Router, types, F, Bot, Dispatcher

from fastapi import Depends
import sys
from pathlib import Path


# Путь к корню проекта (Hakaton_2_sem)
project_root = Path(__file__).parent.parent  # Поднимаемся на два уровня вверх от db_operations
sys.path.append(str(project_root))  # Добавляем корень в sys.path
from Database.db_create import User, Conversation, Message
from Database.db_create import DB_HOST, DB_NAME, DB_PORT, DB_USER, DB_PASSWORD
from keyboards import get_cancel_keyboard
from db_operations.process_messages import process_single_message, embedding_single_message
from config import owners

async def get_sessionmaker(dispatcher: Dispatcher) -> async_sessionmaker[AsyncSession]:
    return dispatcher['async_session_maker']

# Настройки подключения к БД
DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


# Папка для сохранения JSON файлов
JSON_FOLDER = "date_json"
os.makedirs(JSON_FOLDER, exist_ok=True)

# Состояния FSM
class UploadConversation(StatesGroup):
    date = State()
    time = State()
    json_file = State()
    
class UpdateUsernames(StatesGroup):
    waiting_for_username = State()  # Состояние ожидания ввода username
    current_speaker = State()      # Состояние для хранения текущего спикера
    
dboperations_router = Router()


# Обработчик отмены
@dboperations_router.callback_query(F.data == "cancel_upload")
async def cancel_upload(callback: types.CallbackQuery, state: FSMContext):
    print(f"[DEBUG] Cancel pressed by {callback.from_user.id}")
    
    try:
        # Получаем все сохраненные данные
        data = await state.get_data()
        print(f"[DEBUG] Current state data: {data}")
        
        # Удаляем сообщение с кнопкой
        await callback.message.delete()
        
        # Удаляем предыдущие сообщения бота
        if 'last_bot_message_id' in data:
            try:
                await callback.bot.delete_message(
                    chat_id=callback.message.chat.id,
                    message_id=data['last_bot_message_id']
                )
            except Exception as e:
                print(f"[DEBUG] Error deleting bot message: {e}")
        
        # Удаляем сообщение пользователя (если сохранили его ID)
        if 'last_message_id' in data:
            try:
                await callback.bot.delete_message(
                    chat_id=callback.message.chat.id,
                    message_id=data['last_message_id']
                )
            except Exception as e:
                print(f"[DEBUG] Error deleting user message: {e}")
                
    except Exception as e:
        print(f"[DEBUG] Error in cancel handler: {e}")
    
    await callback.answer("Загрузка отменена", show_alert=True)
    await state.clear()
    
    

# Обработчик начала загрузки (с проверкой владельца в начале)
@dboperations_router.message(F.text == "Загрузить новый разговор")
async def start_upload(message: types.Message, state: FSMContext):
    if message.from_user.id not in owners:
        await message.answer("Вы не являетесь владельцем бота")
        return
    
    # Отправляем сообщение с клавиатурой
    msg = await message.answer(
        "Введите дату разговора в формате YYYY-MM-DD",
        reply_markup=get_cancel_keyboard()
    )
    
    # Сохраняем ID сообщения с кнопкой отмены
    await state.update_data(
        last_bot_message_id=msg.message_id,
        cancel_message_id=msg.message_id  # Сохраняем ID сообщения с кнопкой
    )
    await state.set_state(UploadConversation.date)

# Получаем от хозяина Дату разговора
@dboperations_router.message(UploadConversation.date)
async def process_date(message: types.Message, state: FSMContext):
    if not re.match(r'^(19|20)\d\d-(0[1-9]|1[012])-(0[1-9]|[12][0-9]|3[01])$', message.text):
        await message.answer("Неверный формат даты. Пожалуйста, введите дату в формате YYYY-MM-DD (например, 2023-12-31)")
        return
    
    # Удаляем предыдущее сообщение бота
    try:
        data = await state.get_data()
        if 'last_bot_message_id' in data:
            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=data['last_bot_message_id']
            )
    except Exception as e:
        print(f"Ошибка при удалении сообщения: {e}")

    # Отправляем новое сообщение с клавиатурой
    msg = await message.answer(
        "Введите время начала разговора в формате HH:MM (например, 14:30)",
        reply_markup=get_cancel_keyboard()
    )
    
    # Сохраняем ID важных сообщений
    await state.update_data(
        conversation_date=message.text,
        last_message_id=message.message_id,
        last_bot_message_id=msg.message_id,  # Сообщение с кнопкой отмены
        cancel_message_id=msg.message_id     # Дублируем для надежности
    )
    await state.set_state(UploadConversation.time)

# Получаем от хозяина Время начала разговора
@dboperations_router.message(UploadConversation.time)
async def process_time(message: types.Message, state: FSMContext):
    if not re.match(r'^([01][0-9]|2[0-3]):([0-5][0-9])$', message.text):
        await message.answer("Неверный формат времени. Пожалуйста, введите время в формате HH:MM (например, 09:15 или 23:45)")
        return
    
    # Удаляем предыдущее сообщение бота
    try:
        data = await state.get_data()
        if 'last_bot_message_id' in data:
            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=data['last_bot_message_id']
            )
    except Exception as e:
        print(f"Ошибка при удалении сообщения: {e}")

    # Отправляем новое сообщение с клавиатурой
    msg = await message.answer(
        "Приложите файл JSON транскрипции Вашего разговора",
        reply_markup=get_cancel_keyboard()
    )
    
    # Сохраняем ID важных сообщений
    await state.update_data(
        conversation_time=message.text,
        last_message_id=message.message_id,
        last_bot_message_id=msg.message_id,  # Сообщение с кнопкой отмены
        cancel_message_id=msg.message_id     # Дублируем для надежности
    )
    await state.set_state(UploadConversation.json_file)



# Обработчик JSON файла
@dboperations_router.message(UploadConversation.json_file, F.document)
async def process_json_file(
    message: types.Message, 
    state: FSMContext, 
    bot: Bot,
    async_session_maker: async_sessionmaker[AsyncSession] = Depends(get_sessionmaker)
):
    if not message.document.file_name.lower().endswith('.json'):
        await message.answer("Файл должен быть в формате JSON")
        return
    
    try:
        # Получаем сохраненные данные из состояния
        data = await state.get_data()
        
        # Удаляем предыдущие сообщения
        if 'last_bot_message_id' in data:
            await bot.delete_message(
                chat_id=message.chat.id,
                message_id=data['last_bot_message_id']
            )

        # Подготовка файла
        file_name = message.document.file_name
        file_path = os.path.join(JSON_FOLDER, file_name)
        os.makedirs(JSON_FOLDER, exist_ok=True)
        
        await bot.download(
            file=message.document.file_id,
            destination=file_path
        )
        print(f"[DEBUG] Файл {file_name} успешно скачан")

        # Получаем дату и время из состояния
        conversation_date = data['conversation_date']  # Формат YYYY-MM-DD
        conversation_time = data['conversation_time']  # Формат HH:MM
        
        # Обработка файла
        async with async_session_maker() as session:
            try:
                # Получаем список участников, которым нужно обновить username
                participants_without_username = await process_json_and_insert_data(
                    file_path=file_path,
                    session=session,
                    conversation_date=conversation_date,
                    conversation_time=conversation_time
                )
                await session.commit()
                
                # Сохраняем информацию о conversation_id для последующего обновления
                conversation_id = await get_next_conversation_id(session) - 1
                
                await message.answer(f"✅ Файл {file_name} успешно обработан\nДанные сохранены в БД")
                
                # Если есть участники без username, запрашиваем их
                if participants_without_username:
                    await state.update_data(
                        conversation_id=conversation_id,
                        participants_to_update=participants_without_username
                    )
                    await ask_for_usernames(message, state, participants_without_username)
                else:
                    await state.clear()
                    
            except Exception as db_error:
                await session.rollback()
                raise db_error
                
    except Exception as e:
        error_msg = f"Ошибка при обработке файла: {str(e)}"
        print(f"[ERROR] {error_msg}")
        await message.answer(f"❌ {error_msg}")
    finally:
        if 'participants_to_update' not in (await state.get_data()):
            await state.clear()
            print(f"[DEBUG] Состояние FSM очищено")
            

async def ask_for_usernames(message: types.Message, state: FSMContext, participants: list):
    """Отправляет сообщение с кнопками для выбора участника, которому нужно указать username"""
    # Удаляем предыдущие сообщения с кнопками
    data = await state.get_data()
    if 'username_messages' in data:
        try:
            for msg_id in data['username_messages']:
                await message.bot.delete_message(
                    chat_id=message.chat.id,
                    message_id=msg_id
                )
        except Exception as e:
            print(f"Ошибка при удалении предыдущих сообщений: {e}")
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[])
    
    for participant in participants:
        keyboard.inline_keyboard.append([
            types.InlineKeyboardButton(
                text=participant['name'],
                callback_data=f"set_username:{participant['id']}:{participant['name']}"
            )
        ])
    
    keyboard.inline_keyboard.append([
        types.InlineKeyboardButton(
            text="Завершить (остальные без username)",
            callback_data="usernames_done"
        )
    ])
    
    msg = await message.answer(
        "Необходимо указать tg_username для участников разговора:",
        reply_markup=keyboard
    )
    
    # Сохраняем ID всех сообщений с кнопками
    username_messages = data.get('username_messages', [])
    username_messages.append(msg.message_id)
    await state.update_data(
        last_bot_message_id=msg.message_id,
        username_messages=username_messages
    )


# Обработчик нажатия на кнопку участника
@dboperations_router.callback_query(F.data.startswith("set_username:"))
async def set_username_handler(callback: types.CallbackQuery, state: FSMContext):
    _, user_id, user_name = callback.data.split(":")
    await callback.answer()
    
    await state.update_data(current_speaker={"id": int(user_id), "name": user_name})
    await state.set_state(UpdateUsernames.waiting_for_username)
    
    await callback.message.answer(f"Введите tg_username для {user_name}:")

# Обработчик ввода username
@dboperations_router.message(UpdateUsernames.waiting_for_username)
async def process_username_input(
    message: types.Message, 
    state: FSMContext,
    async_session_maker: async_sessionmaker[AsyncSession] = Depends(get_sessionmaker)
):
    data = await state.get_data()
    speaker = data['current_speaker']
    new_username = message.text.strip()
    
    if new_username.startswith('@'):
        new_username = new_username.replace('@', '')
    
    async with async_session_maker() as session:
        # Проверяем, существует ли уже такой username
        existing_user = await session.execute(
            select(User).where(User.tg_username == new_username)
        )
        existing_user = existing_user.scalar_one_or_none()
        
        current_user = await session.execute(
            select(User).where(User.id == speaker['id'])
        )
        current_user = current_user.scalar_one()
        
        if existing_user:
            # Если username уже существует
            if existing_user.id == current_user.id:
                # Это тот же пользователь, просто обновляем
                current_user.tg_username = new_username
            else:
                # Нужно заменить все ссылки на нового пользователя и удалить текущего
                await session.execute(
                    update(Message)
                    .where(Message.user_id == current_user.id)
                    .values(user_id=existing_user.id)
                )
                
                convs = await session.execute(
                    select(Conversation)
                )
                convs = convs.scalars().all()
                
                for conv in convs:
                    if current_user.id in conv.participants:
                        new_participants = [
                            p for p in conv.participants if p != current_user.id
                        ]
                        if existing_user.id not in new_participants:
                            new_participants.append(existing_user.id)
                        conv.participants = new_participants
                
                await session.delete(current_user)
                
            await message.answer(f"✅ Username {new_username} обновлён")
        else:
            # Просто обновляем username
            current_user.tg_username = new_username
            await message.answer(f"✅ Для {speaker['name']} установлен username: {new_username}")
        
        await session.commit()
        
        # Обновляем список участников, которым нужно указать username
        participants_to_update = data['participants_to_update']
        updated_participants = [
            p for p in participants_to_update 
            if p['id'] != speaker['id']
        ]
        
        if updated_participants:
            await state.update_data(participants_to_update=updated_participants)
            await ask_for_usernames(message, state, updated_participants)
        else:
            # Удаляем все сообщения с кнопками
            if 'username_messages' in data:
                try:
                    for msg_id in data['username_messages']:
                        await message.bot.delete_message(
                            chat_id=message.chat.id,
                            message_id=msg_id
                        )
                except Exception as e:
                    print(f"Ошибка при удалении сообщений: {e}")
            
            await message.answer("✅ Все usernames указаны!")
            await state.clear()
        
        await state.set_state(None)


# Обработчик кнопки "Готово"
@dboperations_router.callback_query(F.data == "usernames_done")
async def usernames_done_handler(
    callback: types.CallbackQuery, 
    state: FSMContext,
    bot: Bot,
    async_session_maker: async_sessionmaker[AsyncSession] = Depends(get_sessionmaker)
):
    try:
        data = await state.get_data()
        
        # Удаляем сообщение с кнопками, на которое нажали "Завершить"
        try:
            await bot.delete_message(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id
            )
        except Exception as e:
            print(f"Ошибка при удалении сообщения с кнопками: {e}")

        # Удаляем все предыдущие сообщения с кнопками из истории
        if 'username_messages' in data:
            try:
                for msg_id in data['username_messages']:
                    # Не пытаемся удалить текущее сообщение еще раз
                    if msg_id != callback.message.message_id:
                        await bot.delete_message(
                            chat_id=callback.message.chat.id,
                            message_id=msg_id
                        )
            except Exception as e:
                print(f"Ошибка при удалении предыдущих сообщений: {e}")

        if 'participants_to_update' not in data or not data['participants_to_update']:
            await callback.answer("Все usernames указаны!", show_alert=True)
            await state.clear()
            return
        
        # Получаем список не указанных имен
        participants_left = [p['name'] for p in data['participants_to_update']]
        participants_left_str = ", ".join(participants_left)
        
        async with async_session_maker() as session:
            # Обновляем оставшихся участников (оставляем tg_username NULL)
            for participant in data['participants_to_update']:
                user = await session.execute(
                    select(User).where(User.id == participant['id'])
                )
                user = user.scalar_one()
                user.tg_username = None  # Теперь столбец поддерживает NULL
                await session.commit()
        
        # Формируем сообщение
        alert_message = (
            f"Участники разговора: {participants_left_str} "
            f"сохранены без указания tg_username"
        )
        
        await callback.answer(alert_message, show_alert=True)
        
        # Отправляем подтверждение в чат
        await bot.send_message(
            chat_id=callback.message.chat.id,
            text=alert_message
        )
        
        # Очищаем состояние
        await state.clear()
        
    except Exception as e:
        print(f"Ошибка в обработчике usernames_done: {e}")
        await callback.answer("Произошла ошибка при обработке", show_alert=True)




async def get_next_conversation_id(session: AsyncSession) -> int:
    """Получает следующий доступный ID для новой беседы"""
    result = await session.execute(select(func.max(Conversation.id)))
    max_id = result.scalar() or 0  # Если нет бесед, начнем с 1
    return max_id + 1




# Модифицируем функцию process_json_and_insert_data
async def process_json_and_insert_data(
    file_path: str,
    session: AsyncSession,
    conversation_date: str,
    conversation_time: str
) -> list:
    """Обрабатывает JSON файл и вставляет данные в БД. 
    Возвращает список участников без username (словари с id и name)."""
    # Получаем следующий ID беседы
    conversation_id = await get_next_conversation_id(session)
    
    # Преобразуем дату и время из строк в объекты
    from datetime import datetime
    conv_date = datetime.strptime(conversation_date, "%Y-%m-%d").date()
    conv_time = datetime.strptime(conversation_time, "%H:%M").time()
    
    # Создаём множество для хранения уникальных ID участников
    participants_ids = set()
    participants_without_username = []
    
    # Загружаем JSON для предварительного анализа участников
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Сначала собираем всех уникальных спикеров из JSON
    speakers = {item['speaker'] for item in data if 'speaker' in item}
    
    # Для каждого спикера находим или создаём пользователя и добавляем его ID
    for speaker in speakers:
        user = await session.execute(
            select(User).where(User.name == speaker)
        )
        user = user.scalar_one_or_none()
        
        if not user:
            user = User(
                name=speaker,
                tg_username=f"unknown_{speaker}"
            )
            session.add(user)
            await session.flush()  # Чтобы получить ID
        
        participants_ids.add(user.id)
        
        # Если у пользователя стандартный username (начинается с unknown_), добавляем в список для обновления
        if user.tg_username.startswith("unknown_"):
            participants_without_username.append({
                'id': user.id,
                'name': user.name
            })
    
    # Создаем беседу с указанной датой, временем и участниками
    conversation = Conversation(
        id=conversation_id,
        date_created=conv_date,
        time_created=conv_time,
        participants=list(participants_ids)  # Преобразуем множество в список
    )
    session.add(conversation)
    
    if not data:
        return participants_without_username
    
    previous_speaker = None
    combined_texts = []
    
    for item in data:
        speaker = item.get('speaker')
        text = item.get('text')
        start = item.get('start')  
        
        if not all([speaker, text, start]):
            continue
        
        # Рассчитываем время сообщения (время начала разговора + offset из JSON)
        start_seconds = int(start)
        total_seconds = conv_time.hour * 3600 + conv_time.minute * 60 + int(start_seconds/1000)
        hours = total_seconds // 3600 % 24
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        message_time = time(hour=hours, minute=minutes, second=seconds)
        
        if speaker == previous_speaker:
            combined_texts.append(text)
            continue
            
        # Обрабатываем накопленные сообщения
        if combined_texts:
            await process_speaker_messages(
                session=session,
                speaker=previous_speaker,
                texts=combined_texts,
                conversation_id=conversation_id,
                current_date=conv_date,
                message_time=message_time
            )
            
        combined_texts = [text]
        previous_speaker = speaker
    
    # Обрабатываем последнего спикера
    if combined_texts and previous_speaker:
        await process_speaker_messages(
            session=session,
            speaker=previous_speaker,
            texts=combined_texts,
            conversation_id=conversation_id,
            current_date=conv_date,
            message_time=message_time
        )
    
    return participants_without_username


async def process_speaker_messages(
    session: AsyncSession,
    speaker: str,
    texts: list[str],
    conversation_id: int,
    current_date: date,
    message_time: time
):
    """Вспомогательная функция для обработки сообщений спикера"""
    user = await session.execute(
        select(User).where(User.name == speaker)
    )
    user = user.scalar_one_or_none()
    
    if not user:
        user = User(
            name=speaker,
            tg_username=f"unknown_{speaker}"
        )
        session.add(user)
        await session.flush()
    
    # Объединяем тексты
    raw_text = '/'.join(texts)
    
    # Обрабатываем текст
    processed_text = await process_single_message(raw_text)
    
    # Получаем эмбеддинг
    embedding = await embedding_single_message(processed_text)
    
    message = Message(
        user_id=user.id,
        conversation_id=conversation_id,
        text=raw_text,
        date=current_date,
        time=message_time,
        processed_text=processed_text,
        embeddings=embedding  # Добавляем эмбеддинг
    )
    session.add(message)
    
async def get_message_contexts(
    message_tuples: list[tuple[str, str, float]], 
    session: AsyncSession
) -> str:
    """
    Формирует контекст для каждого сообщения из списка кортежей.
    
    Args:
        message_tuples: Список кортежей (текст, обработанный текст, оценка сходства)
        session: Асинхронная сессия SQLAlchemy
        
    Returns:
        Строка с контекстом для каждого сообщения в требуемом формате
    """
    result = []
    
    for text, processed_text, similarity in message_tuples:
        # Находим сообщение из кортежа в базе
        message_query = select(Message).where(
            and_(
                Message.text == text,
                Message.processed_text == processed_text
            )
        )
        message = (await session.execute(message_query)).scalar_one_or_none()
        
        if not message:
            continue
            
        # Получаем информацию о беседе
        conv_query = select(Conversation).where(Conversation.id == message.conversation_id)
        conversation = (await session.execute(conv_query)).scalar_one()
        
        # Получаем информацию об авторе
        user_query = select(User).where(User.id == message.user_id)
        user = (await session.execute(user_query)).scalar_one()
        
        # Форматируем дату и время беседы
        conv_date_time = (
            f"{conversation.date_created.strftime('%Y-%m-%d')} "
            f"{conversation.time_created.strftime('%H:%M:%S')}"
        )
        
        # Получаем все сообщения из этой беседы в хронологическом порядке
        messages_query = (
            select(Message)
            .where(Message.conversation_id == message.conversation_id)
            .order_by(Message.date.asc(), Message.time.asc())
        )
        all_messages = (await session.execute(messages_query)).scalars().all()
        
        # Находим индекс текущего сообщения
        try:
            current_idx = [m.id for m in all_messages].index(message.id)
        except ValueError:
            continue
            
        # Формируем список сообщений для вывода
        output_messages = []
        
        # 2 предыдущих сообщения
        prev_messages = all_messages[max(0, current_idx-2):current_idx]
        for msg in prev_messages:
            user_query = select(User).where(User.id == msg.user_id)
            msg_user = (await session.execute(user_query)).scalar_one()
            output_messages.append(f"{msg_user.name}: {msg.text}")
            
        # Текущее сообщение
        output_messages.append(f"{user.name}: {message.text} [similarity: {similarity:.2f}]")
        
        # 5 последующих сообщений
        next_messages = all_messages[current_idx+1:current_idx+6]
        for msg in next_messages:
            user_query = select(User).where(User.id == msg.user_id)
            msg_user = (await session.execute(user_query)).scalar_one()
            output_messages.append(f"{msg_user.name}: {msg.text}")
            
        # Формируем блок для этого сообщения
        block = [
            f"Дата и время разговора: {conv_date_time}",
            *output_messages,
            ""  # Пустая строка для разделения блоков
        ]
        
        result.append("\n".join(block))
    
    return "\n".join(result)
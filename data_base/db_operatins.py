import json
from datetime import datetime, time, date
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from sqlalchemy import func

import asyncio
import sys
from pathlib import Path

# Путь к корню проекта (Hakaton_2_sem)
project_root = Path(__file__).parent.parent  # Поднимаемся на два уровня вверх от db_operations
sys.path.append(str(project_root))  # Добавляем корень в sys.path

from Database.db_create import User, Conversation, Message
from Database.db_create import DB_HOST, DB_NAME, DB_PORT, DB_USER, DB_PASSWORD



# Настройки подключения к БД
DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Создаем асинхронный движок
engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_next_conversation_id(async_session: AsyncSession) -> int:
    """Получает следующий доступный ID для новой беседы"""
    result = await async_session.execute(select(func.max(Conversation.id)))
    max_id = result.scalar() or 0  # Если нет бесед, начнем с 1
    return max_id + 1

async def process_json_and_insert_data(json_file_path: str):
    """Обрабатывает JSON файл и вставляет данные в БД с новым conversation_id"""
    async with async_session() as session:
        # Получаем следующий доступный ID беседы
        conversation_id = await get_next_conversation_id(session)
        
        # Загружаем JSON файл
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not data:
            return
        
        current_date = date.today()
        
        # Создаем новую беседу
        conversation = Conversation(
            id=conversation_id,
            date_created=current_date,
            time_created=time(0, 0),  # Время по умолчанию
            participants=[]  # Пока пустой массив
        )
        session.add(conversation)
        await session.commit()
        
        previous_speaker = None
        combined_texts = []
        first_start_time = None
        
        for item in data:
            speaker = item.get('speaker')
            text = item.get('text')
            start = item.get('start')
            
            if not all([speaker, text, start]):
                continue
            
            # Преобразуем время start из секунд в объект time
            total_seconds = int(start)
            hours = total_seconds // 3600
            remaining_seconds = total_seconds % 3600
            minutes = remaining_seconds // 60
            seconds = remaining_seconds % 60

            # Обеспечиваем, что часы будут в диапазоне 0-23
            hours = hours % 24
            start_time = time(hours, minutes, seconds)
            
            # Если speaker такой же, как предыдущий, объединяем тексты
            if speaker == previous_speaker:
                combined_texts.append(text)
                continue
            else:
                # Если есть накопленные тексты от предыдущего speaker, сохраняем их
                if combined_texts:
                    user = await session.execute(
                        select(User).where(User.name == previous_speaker)
                    )
                    user = user.scalar_one_or_none()
                    
                    if not user:
                        user = User(
                            name=previous_speaker,
                            tg_username=f"unknown_{previous_speaker}"
                        )
                        session.add(user)
                        await session.commit()
                        await session.refresh(user)
                    
                    message = Message(
                        user_id=user.id,
                        conversation_id=conversation_id,
                        text='/'.join(combined_texts),
                        date=current_date,
                        time=first_start_time,
                        processed_text=None,
                        embeddings=None
                    )
                    session.add(message)
                
                # Сбрасываем для нового speaker
                combined_texts = [text]
                first_start_time = start_time
                previous_speaker = speaker
        
        # Обрабатываем последний накопленный текст
        if combined_texts and previous_speaker:
            user = await session.execute(
                select(User).where(User.name == previous_speaker)
            )
            user = user.scalar_one_or_none()
            
            if not user:
                user = User(
                    name=previous_speaker,
                    tg_username=f"unknown_{previous_speaker}"
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
            
            message = Message(
                user_id=user.id,
                conversation_id=conversation_id,
                text='/'.join(combined_texts),
                date=current_date,
                time=first_start_time,
                processed_text=None,
                embeddings=None
            )
            session.add(message)
        
        await session.commit()

async def main():
    await process_json_and_insert_data('date_json/transcription.json')

if __name__ == "__main__":
    asyncio.run(main())
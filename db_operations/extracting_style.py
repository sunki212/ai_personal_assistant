from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from Database.db_create import User, Conversation, Message  # Импортируем модели

async def get_conversation_messages(
    username_owner: str,
    username_guest: str,
    session: AsyncSession
) -> str:
    # Получаем id пользователей
    owner_query = select(User.id).where(User.tg_username == username_owner)  # Используем User
    guest_query = select(User.id).where(User.tg_username == username_guest)  # Используем User
    
    owner_id = (await session.execute(owner_query)).scalar()
    guest_id = (await session.execute(guest_query)).scalar()
    print(owner_id, guest_id)
    if not owner_id or not guest_id:
        return "Один из пользователей не найден"
    
    # Находим 3 последние беседы между этими пользователями
    conv_query = (
        select(Conversation.id)  # Используем Conversation
        .where(Conversation.participants.contains([owner_id, guest_id]))
        .order_by(Conversation.date_created.desc(), Conversation.time_created.desc())
        .limit(3)
    )
    
    conv_ids = (await session.execute(conv_query)).scalars().all()
    
    if not conv_ids:
        return "Беседы между пользователями не найдены"
    
    result = []
    
    for i, conv_id in enumerate(conv_ids, 1):
        # Получаем первые 5 сообщений
        first_messages_query = (
            select(Message.text)  # Используем Message
            .where(Message.conversation_id == conv_id)
            .order_by(Message.date.asc(), Message.time.asc())
            .limit(5)
        )
        first_messages = (await session.execute(first_messages_query)).scalars().all()
        
        # Получаем последние 5 сообщений
        last_messages_query = (
            select(Message.text)  # Используем Message
            .where(Message.conversation_id == conv_id)
            .order_by(Message.date.desc(), Message.time.desc())
            .limit(5)
        )
        last_messages = (await session.execute(last_messages_query)).scalars().all()
        last_messages.reverse()  # Чтобы сохранить хронологический порядок
        
        # Объединяем и обрезаем сообщения
        all_messages = first_messages + last_messages
        trimmed_messages = [msg[:200] for msg in all_messages]
        
        # Формируем результат для этой беседы
        conv_result = [f"Беседа {i}"]
        conv_result.extend(trimmed_messages)
        
        result.append("\n".join(conv_result))
    
    return "\n\n".join(result)

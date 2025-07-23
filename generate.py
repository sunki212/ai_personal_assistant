from typing import Dict, List
from dataclasses import dataclass
from openai import AsyncOpenAI
from config import DEESEEK_API_KEY1, ADMIN_GROUP_ID, owner_username
from aiogram import Bot
from models import UserData
from db_operations.extracting_style import get_conversation_messages
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from fastapi import Depends
from sqlalchemy.ext.asyncio import async_sessionmaker
from db_operations.db_operatins import get_sessionmaker

import json
import os

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=DEESEEK_API_KEY1,
)

user_contexts: Dict[int, List[dict]] = {}

@dataclass
class ChatContext:
    messages: List[dict]
    max_length: int = 200


async def ai_generate(
    user_id: int,
    username: str,
    text: str,
    bot: Bot,
    user_data: UserData,
    promt_type: str,
    session_maker: async_sessionmaker[AsyncSession]  # Без значения по умолчанию
) -> str:
    if user_id not in user_contexts:
        user_contexts[user_id] = ChatContext(messages=[])
    
    context = user_contexts[user_id]

    def load_prompt(promt_type: str) -> str:
        if os.path.exists("promts.json"):
            with open("promts.json", "r", encoding="utf-8") as file:
                prompts = json.load(file)
                return prompts.get(promt_type, "")
        return ""
    
    if len(context.messages) == 0:
        promt = load_prompt(promt_type)
        
        # Получаем историю сообщений из БД
        conversation_history = ""
        try:
            async with session_maker() as session:
                conversation_history = await get_conversation_messages(
                    username_owner=owner_username,
                    username_guest=username,
                    session=session
                )
                print(conversation_history)
                # Добавляем историю к промту только если она не пустая
                if conversation_history and not conversation_history.startswith(("Один из пользователей не найден", "Беседы между пользователями не найдены")):
                    promt = promt.replace('{пример реальных сообщений Владимира Викторовича}', conversation_history)
                
                    
        except Exception as e:
            print(f"Ошибка при получении истории бесед: {e}")
            if ADMIN_GROUP_ID:
                try:
                    await bot.send_message(ADMIN_GROUP_ID, f"Ошибка при получении истории бесед: {e}")
                except Exception as send_error:
                    print(f"Не удалось отправить сообщение админу: {send_error}")
        
        if promt_type == "The_main_promt":
            context.messages.append({"role": "system", "content": promt})

    context.messages.append({"role": "user", "content": text})

    if len(context.messages) > context.max_length * 2:
        context.messages = context.messages[-context.max_length * 2:]

    try:
        completion = await client.chat.completions.create(
            model="deepseek/deepseek-chat-v3-0324:free",
            messages=context.messages
        )

        assistant_response = completion.choices[0].message.content
        context.messages.append({"role": "assistant", "content": assistant_response})
        
        return assistant_response
        
    except Exception as e:
        error_msg = f"🚨 Critical API Error: {str(e)}"
        print(error_msg)
        if ADMIN_GROUP_ID:
            try:
                await bot.send_message(ADMIN_GROUP_ID, error_msg)
            except Exception as send_error:
                print(f"Не удалось отправить сообщение админу: {send_error}")
        return "Произошла ошибка при генерации ответа. Мы уже работаем над исправлением!"

def clear_context(user_id: int):
    user_contexts.pop(user_id, None)
from typing import Dict, List
from dataclasses import dataclass
from openai import AsyncOpenAI
from config import DEESEEK_API_KEY1, ADMIN_GROUP_ID
from aiogram import Bot
from models import UserData
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



async def ai_generate(user_id: int, text: str, bot: Bot, user_data: UserData, promt_type: str) -> str:
    if user_id not in user_contexts:
        user_contexts[user_id] = ChatContext(messages=[])
    
    context = user_contexts[user_id]

    def load_prompt(promt_type: str) -> str:
        if os.path.exists("prompts.json"):
            with open("prompts.json", "r", encoding="utf-8") as file:
                prompts = json.load(file)
                return prompts.get(promt_type, "")
        return ""
    
    if len(context.messages) == 0:
        promt = load_prompt(promt_type)
        if promt_type == "The_main_promt":
            context.messages.append({"role": "system", "content": promt})

    context.messages.append({"role": "user", "content": text})

    if len(context.messages) > context.max_length * 2:
        context.messages = context.messages[-context.max_length * 2:]

    try:
        completion = await client.chat.completions.create(
            model="deepseek/deepseek-chat:free",
            messages=context.messages
        )

        assistant_response = completion.choices[0].message.content
        context.messages.append({"role": "assistant", "content": assistant_response})
        
        return assistant_response
        
    except Exception as e:
        error_msg = f"🚨 Critical API Error: {str(e)}"
        print(error_msg)
        await bot.send_message(ADMIN_GROUP_ID, error_msg)
        return "Произошла ошибка при генерации ответа. Мы уже работаем над исправлением!"

def clear_context(user_id: int):
    user_contexts.pop(user_id, None)
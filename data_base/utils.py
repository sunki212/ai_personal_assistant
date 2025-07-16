import logging
import os
import json

logger = logging.getLogger(__name__)

def load_prompt_by_key(prompt_type: str) -> str:
    """
    Загружает текст промта по ключу из файла prompts.json.
    Возвращает пустую строку, если файл или ключ не найден.
    """
    try:
        if os.path.exists("prompts.json"):
            with open("prompts.json", "r", encoding="utf-8") as f:
                prompts = json.load(f)
                return prompts.get(prompt_type, "")
    except Exception as e:
        print(f"Ошибка при чтении prompts.json: {e}")
    return ""
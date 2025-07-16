import json
from pathlib import Path
from typing import Dict

# Путь к JSON-файлу (создастся автоматически)
APPLICATIONS_JSON = Path("lists_of_users/applications.json")
BLACKLIST_JSON = Path("lists_of_users/blacklist.json")
ADMITTED_JSON = Path("lists_of_users/admitted.json")


def load_applications() -> Dict[str, str]:
    """Загружает данные из JSON-файла или возвращает пустой словарь."""
    try:
        with open(APPLICATIONS_JSON, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    
def load_blacklist() -> Dict[str, str]:
    """Загружает данные из JSON-файла или возвращает пустой словарь."""
    try:
        with open(BLACKLIST_JSON, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    
def load_admitted() -> Dict[str, str]:
    """Загружает данные из JSON-файла или возвращает пустой словарь."""
    try:
        with open(ADMITTED_JSON, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_applications(data: Dict[str, str]) -> None:
    """Сохраняет словарь в JSON-файл."""
    with open(APPLICATIONS_JSON, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
        
def save_blacklist(data: Dict[str, str]) -> None:
    """Сохраняет словарь в JSON-файл."""
    with open(BLACKLIST_JSON, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
        
def save_admitted(data: Dict[str, str]) -> None:
    """Сохраняет словарь в JSON-файл."""
    with open(ADMITTED_JSON, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


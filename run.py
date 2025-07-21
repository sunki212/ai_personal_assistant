import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from typing import Dict
import nltk

from Database.db_create import init_db
from handlers.handlers import handlers_router
from handlers.request_handler import application_router
from handlers.owner_handlers import owners_router
from db_operations.db_operatins import dboperations_router
from lists_of_users.create_JSON_lists import load_applications, load_blacklist, load_admitted
from config import TOKEN  # API ключ телеграмма



async def main():
    
    try:
        nltk.download('punkt')
        nltk.download('stopwords')
        nltk.download('wordnet')
        print("NLTK resources downloaded successfully")
    except Exception as e:
        print(f"Error downloading NLTK resources: {e}")
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    
    dp = Dispatcher()
    dp.include_router(dboperations_router) 
    dp.include_router(handlers_router)
    dp.include_router(application_router)
    dp.include_router(owners_router)

    # Инициализируем базу данных и получаем engine и sessionmaker
    engine, async_session_maker = await init_db()
    
    applications: Dict[str, str] = load_applications()
    blacklist: Dict[str, str] = load_blacklist()
    list_of_users: Dict[str, str] = load_admitted()
    
    # Сохраняем engine и sessionmaker в диспетчере для дальнейшего использования
    dp['applications'] = applications
    dp['blacklist'] = blacklist
    dp['list_of_users'] = list_of_users
    dp['async_session_maker'] = async_session_maker
    
    # Запускаем polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
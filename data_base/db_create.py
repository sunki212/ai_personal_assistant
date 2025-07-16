import os
from sqlalchemy import Column, Integer, String, ForeignKey, Text, Float, Date, Time
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import text
import docker
import time
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import asyncio

# Конфигурация базы данных
DB_NAME = "vector_db"
DB_USER = "postgres"
DB_PASSWORD = "postgres"
DB_HOST = "localhost"
DB_PORT = 5432
CONTAINER_NAME = "pgvector_db"
IMAGE_NAME = "agent/pgvector"

# Настраиваем SQLAlchemy
Base = declarative_base()

# Определяем модели таблиц
class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=True)
    tg_username = Column(String, nullable=False)

class Conversation(Base):
    __tablename__ = 'conversation'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date_created = Column(Date)
    time_created = Column(Time, nullable=False)
    participants = Column(ARRAY(Integer))

class Message(Base):
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    conversation_id = Column(Integer, ForeignKey('conversation.id'), nullable=False)
    text = Column(Text, nullable=False)
    date = Column(Date, nullable=False)
    time = Column(Time, nullable=False)
    processed_text = Column(Text, nullable=True)
    embeddings = Column(ARRAY(Float), nullable=True)

def setup_docker_container():
    try:
        client = docker.from_env()
        client.ping()
        print("Docker работает, продолжаем...")
        
        try:
            client.images.get(IMAGE_NAME)
            print(f"Образ {IMAGE_NAME} найден")
        except docker.errors.ImageNotFound:
            raise RuntimeError(
                f"Образ {IMAGE_NAME} не найден. Сначала соберите его используя:\n"
                f"docker build -t {IMAGE_NAME} ."
            )
        
        try:
            container = client.containers.get(CONTAINER_NAME)
            if container.status != "running":
                container.start()
            print(f"Контейнер {CONTAINER_NAME} уже существует и запущен")
            return container
        except docker.errors.NotFound:
            pass
        
        print(f"Создаём новый контейнер из образа {IMAGE_NAME}...")
        container = client.containers.run(
            IMAGE_NAME,
            name=CONTAINER_NAME,
            environment={
                "POSTGRES_USER": DB_USER,
                "POSTGRES_PASSWORD": DB_PASSWORD,
                "POSTGRES_DB": DB_NAME
            },
            ports={'5432/tcp': DB_PORT},
            detach=True,
            volumes={
                'pgdata': {'bind': '/var/lib/postgresql/data', 'mode': 'rw'}
            }
        )
        print(f"Контейнер {container.id} создан и запущен")
        time.sleep(15)
        return container
        
    except docker.errors.DockerException as e:
        print(f"Ошибка Docker: {e}")
        print("Убедитесь, что Docker Desktop установлен и запущен")
        raise
    
def wait_for_postgres(max_retries=10, delay=5):
    for attempt in range(max_retries):
        try:
            with psycopg2.connect(
                user="postgres",
                password="postgres",
                host="localhost",
                port=5432,
                database="postgres"
            ) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
            return True
        except psycopg2.OperationalError:
            print(f"Попытка {attempt + 1}/{max_retries}: PostgreSQL ещё не готов...")
            time.sleep(delay)
    return False

def setup_database():
    if not wait_for_postgres():
        raise RuntimeError("PostgreSQL не стал доступен после ожидания")
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            with psycopg2.connect(
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME
            ) as conn:
                conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                with conn.cursor() as cursor:
                    cursor.execute("""
                        CREATE EXTENSION IF NOT EXISTS vector;
                        CREATE EXTENSION IF NOT EXISTS plpython3u;
                        CREATE EXTENSION IF NOT EXISTS pg_trgm;
                    """)
                    print("Расширения успешно созданы")
                    return True
        except psycopg2.Error as e:
            print(f"Попытка {attempt + 1}/{max_retries}: Ошибка: {e}")
            time.sleep(5)
    
    raise RuntimeError("Не удалось настроить БД после нескольких попыток")

async def init_db():
    # Настраиваем Docker контейнер
    setup_docker_container()
    
    # Создаём базу данных и расширения
    setup_database()
    
    # Строка подключения для асинхронного подключения
    DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    try:
        # Создаём асинхронный движок
        engine = create_async_engine(DATABASE_URL, echo=True)
        
        # Создаём фабрику сессий
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        
        # Создаём таблицы
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            print("Таблицы успешно созданы")
            
            # Добавляем комментарий к столбцу embeddings
            await conn.execute(text("""
                COMMENT ON COLUMN messages.embeddings IS 'VECTOR(768)'
            """))
            print("Установлена размерность вектора 768 для столбца embeddings")
        
        return engine, async_session
    
    except ImportError as e:
        print("\nОШИБКА: Не удалось импортировать модуль asyncpg")
        print("Убедитесь, что вы установили все необходимые зависимости:")
        print("pip install asyncpg sqlalchemy[asyncio]")
        raise

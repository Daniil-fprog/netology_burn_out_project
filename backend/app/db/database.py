import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Создаём папку db_store, если её нет
os.makedirs("db_store", exist_ok=True)

# === Настройка подключения к БД ===
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./db_store/mood_sync.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для создания таблиц
Base = declarative_base()

# === Получение подключения к БД ===
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()

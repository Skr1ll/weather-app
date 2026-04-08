from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Подключение к SQLite (файловая база данных)
DATABASE_URL = "sqlite:///./weather.db"

# Создаём подключение к базе данных
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Создаём фабрику сессий (для работы с БД)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для моделей
Base = declarative_base()


# Модель таблицы "weather_requests" (история запросов)
class WeatherRequest(Base):
    __tablename__ = "weather_requests"

    id = Column(Integer, primary_key=True, index=True)
    city = Column(String, nullable=False)
    temperature = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)


# Создаём все таблицы в базе данных
Base.metadata.create_all(bind=engine)


# Функция для получения сессии БД (используется в main.py)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
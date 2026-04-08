import httpx
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
import os

# Получаем URL базы данных из переменных окружения
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./weather.db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Модель таблицы
class WeatherRequest(Base):
    __tablename__ = "weather_requests"

    id = Column(Integer, primary_key=True, index=True)
    city = Column(String, nullable=False)
    temperature = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)


# Создаём таблицы
Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ========== КООРДИНАТЫ ГОРОДОВ (с большой буквы) ==========

CITY_COORDINATES = {
    "Moscow": {"lat": 55.7558, "lon": 37.6173},
    "London": {"lat": 51.5074, "lon": -0.1278},
    "New York": {"lat": 40.7128, "lon": -74.0060},
    "Tokyo": {"lat": 35.6895, "lon": 139.6917},
    "Paris": {"lat": 48.8566, "lon": 2.3522},
    "Berlin": {"lat": 52.5200, "lon": 13.4050},
    "Rome": {"lat": 41.9028, "lon": 12.4964},
    "Madrid": {"lat": 40.4168, "lon": -3.7038},
    "Dubai": {"lat": 25.2048, "lon": 55.2708},
    "Beijing": {"lat": 39.9042, "lon": 116.4074},
    "Delhi": {"lat": 28.6139, "lon": 77.2090},
    "Sydney": {"lat": -33.8688, "lon": 151.2093},
    "Rio": {"lat": -22.9068, "lon": -43.1729},
    "Cape Town": {"lat": -33.9249, "lon": 18.4241},
    "Istanbul": {"lat": 41.0082, "lon": 28.9784},
}

app = FastAPI(title="Weather Service")


@app.get("/")
def home():
    return {
        "message": "Weather Service with Docker, PostgreSQL",
        "available_cities": list(CITY_COORDINATES.keys())
    }


@app.get("/weather/{city_name}")
async def get_weather(city_name: str, db: Session = Depends(get_db)):
    # Проверяем, есть ли город в словаре (точное совпадение с большой буквы)
    if city_name not in CITY_COORDINATES:
        available = ", ".join(CITY_COORDINATES.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Город '{city_name}' не найден. Доступные города: {available}"
        )

    # Получаем координаты города
    coords = CITY_COORDINATES[city_name]

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": coords["lat"],
        "longitude": coords["lon"],
        "current_weather": True
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        data = response.json()

    current_temp = data["current_weather"]["temperature"]

    new_request = WeatherRequest(
        city=city_name,
        temperature=current_temp
    )
    db.add(new_request)
    db.commit()

    return {
        "city": city_name,
        "temperature_celsius": current_temp,
        "message": f"Сохранено в базу данных для города {city_name}!"
    }


@app.get("/history")
def get_history(db: Session = Depends(get_db)):
    history = db.query(WeatherRequest).order_by(WeatherRequest.timestamp.desc()).limit(50).all()
    return [
        {
            "city": h.city,
            "temperature": h.temperature,
            "timestamp": h.timestamp.isoformat()
        }
        for h in history
    ]


@app.get("/history/{city_name}")
def get_history_by_city(city_name: str, db: Session = Depends(get_db)):
    """История запросов для конкретного города"""
    history = db.query(WeatherRequest).filter(
        WeatherRequest.city == city_name
    ).order_by(WeatherRequest.timestamp.desc()).limit(30).all()

    return [
        {
            "city": h.city,
            "temperature": h.temperature,
            "timestamp": h.timestamp.isoformat()
        }
        for h in history
    ]


@app.get("/cities")
def get_available_cities():
    """Список всех доступных городов"""
    return {
        "cities": list(CITY_COORDINATES.keys()),
        "count": len(CITY_COORDINATES)
    }
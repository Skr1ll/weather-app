import httpx
from fastapi import FastAPI, Depends
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


app = FastAPI(title="Weather Service")


@app.get("/")
def home():
    return {"message": "Weather Service with Docker, PostgreSQL, Prometheus, Grafana"}


@app.get("/weather/{city_name}")
async def get_weather(city_name: str, db: Session = Depends(get_db)):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": 55.75,
        "longitude": 37.62,
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
        "message": "Saved to PostgreSQL!"
    }


@app.get("/history")
def get_history(db: Session = Depends(get_db)):
    history = db.query(WeatherRequest).order_by(WeatherRequest.timestamp.desc()).limit(20).all()
    return [
        {
            "city": h.city,
            "temperature": h.temperature,
            "timestamp": h.timestamp.isoformat()
        }
        for h in history
    ]
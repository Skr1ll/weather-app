import httpx
from fastapi import FastAPI, Depends, Request, Response
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
import os
import time
from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY

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

Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

# Счётчик ошибок
errors_total = Counter(
    'errors_total',
    'Total errors by type',
    ['error_type', 'endpoint']
)


http_request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)
)

# Счётчик запросов к Open-Meteo API
api_calls_total = Counter(
    'api_calls_total',
    'Total calls to Open-Meteo API',
    ['city']
)


active_requests = Gauge(
    'active_requests',
    'Currently processing requests'
)

last_temperature = Gauge(
    'last_temperature_celsius',
    'Last measured temperature',
    ['city']
)

db_size_bytes = Gauge(
    'db_size_bytes',
    'Database file size in bytes'
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    active_requests.inc()  # Увеличиваем счётчик активных запросов
    start_time = time.time()

    try:
        response = await call_next(request)

        # Записываем метрики
        duration = time.time() - start_time
        http_request_duration.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)

        http_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code
        ).inc()

        return response

    except Exception as e:
        # Считаем ошибки
        errors_total.labels(
            error_type=type(e).__name__,
            endpoint=request.url.path
        ).inc()
        raise
    finally:
        active_requests.dec()  # Уменьшаем счётчик


# Эндпоинт для Prometheus (чтобы собирать метрики)
@app.get("/metrics")
async def get_metrics():
    # Обновляем размер базы данных
    if os.path.exists("./weather.db"):
        db_size_bytes.set(os.path.getsize("./weather.db"))

    return Response(generate_latest(REGISTRY), media_type="text/plain")


app = FastAPI(
    title="Weather Service",
    description="Сервис погоды с метриками Prometheus",
    version="1.0.0"
)


@app.get("/")
def home():
    return {"message": "Weather Service with Docker, PostgreSQL, Prometheus, Grafana"}


@app.get("/weather/{city_name}")
async def get_weather(city_name: str, db: Session = Depends(get_db)):
    # Считаем вызов API
    api_calls_total.labels(city=city_name).inc()

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

    # Сохраняем последнюю температуру в метрику
    last_temperature.labels(city=city_name).set(current_temp)

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
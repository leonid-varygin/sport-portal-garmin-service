from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import json

from app.config import settings
from app.routes import auth, activities
from app.services.garmin_service import GarminService


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Инициализация сервисов при запуске
    app.state.garmin_service = GarminService()
    yield
    # Очистка при выключении
    pass


app = FastAPI(
    title="Garmin Service API",
    description="Микросервис для интеграции с Garmin Connect",
    version="1.0.0",
    lifespan=lifespan
)

# Настройка CORS для доступа с фронтенда
try:
    allowed_origins = json.loads(settings.allowed_origins)
except (json.JSONDecodeError, TypeError):
    allowed_origins = ["http://localhost:3000", "http://localhost:8080"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутов
app.include_router(auth.router, prefix="/auth", tags=["authentication"])
app.include_router(activities.router, prefix="/activities", tags=["activities"])


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {"status": "healthy", "service": "garmin-service"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        reload=True
    )

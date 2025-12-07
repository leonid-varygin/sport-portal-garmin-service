import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .routes.auth import router as auth_router, start_background_tasks
from .models.garmin_models import HealthCheckResponse

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Запуск при старте
    logger.info("Starting Garmin Auth Service...")
    
    # Запуск фоновых задач
    try:
        start_background_tasks()
        logger.info("Background tasks started successfully")
    except Exception as e:
        logger.error(f"Failed to start background tasks: {str(e)}")
    
    yield
    
    # Очистка при остановке
    logger.info("Shutting down Garmin Auth Service...")


# Создание FastAPI приложения
app = FastAPI(
    title="Garmin Auth Service",
    description="Сервис авторизации Garmin Connect для интеграции с спортивным порталом",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Глобальный обработчик исключений
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global exception handler: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc) if settings.DEBUG else "An unexpected error occurred"
        }
    )


# Health check endpoint
@app.get("/health", response_model=HealthCheckResponse, tags=["health"])
async def health_check():
    """
    Проверка здоровья сервиса
    
    Returns:
        HealthCheckResponse: Статус сервиса
    """
    try:
        return HealthCheckResponse(
            status="healthy",
            version="1.0.0"
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="Service unavailable"
        )


@app.get("/", tags=["root"])
async def root():
    """
    Корневой эндпоинт
    
    Returns:
        Dict: Информация о сервисе
    """
    return {
        "service": "Garmin Auth Service",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


# Подключение роутов
app.include_router(auth_router)


# Стартовая информация
@app.on_event("startup")
async def startup_event():
    """События при старте приложения"""
    logger.info("Garmin Auth Service started successfully")
    logger.info(f"Documentation available at: {settings.DOCS_URL}")
    logger.info(f"Health check at: {settings.HEALTH_URL}")


@app.on_event("shutdown")
async def shutdown_event():
    """События при остановке приложения"""
    logger.info("Garmin Auth Service shutting down...")


if __name__ == "__main__":
    import uvicorn
    
    # Запуск сервера
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True
    )

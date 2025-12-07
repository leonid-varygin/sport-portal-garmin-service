import os
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Базовые настройки
    DEBUG: bool = Field(default=False, env="DEBUG")
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Настройки сервера
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8002, env="PORT")
    
    # URL настройки
    DOCS_URL: str = Field(default="/docs", env="DOCS_URL")
    HEALTH_URL: str = Field(default="/health", env="HEALTH_URL")
    
    # CORS настройки
    ALLOWED_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080", "http://localhost:9000"],
        env="ALLOWED_ORIGINS"
    )
    
    # Безопасность
    API_KEY: str = Field(default="garmin-service-secret-key", env="API_KEY")
    
    # Настройки сессий
    SESSION_TIMEOUT_HOURS: int = Field(default=1, env="SESSION_TIMEOUT_HOURS")
    MAX_ACTIVE_SESSIONS: int = Field(default=1000, env="MAX_ACTIVE_SESSIONS")
    
    # Настройки очистки
    CLEANUP_INTERVAL_MINUTES: int = Field(default=5, env="CLEANUP_INTERVAL_MINUTES")
    
    # Garmin Connect настройки
    GARMIN_CONNECT_TIMEOUT: int = Field(default=30, env="GARMIN_CONNECT_TIMEOUT")
    GARMIN_CONNECT_RETRIES: int = Field(default=3, env="GARMIN_CONNECT_RETRIES")
    
    # Настройки логирования
    LOG_FILE: Optional[str] = Field(default=None, env="LOG_FILE")
    LOG_MAX_SIZE: int = Field(default=10485760, env="LOG_MAX_SIZE")  # 10MB
    LOG_BACKUP_COUNT: int = Field(default=5, env="LOG_BACKUP_COUNT")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra='ignore'
    )


# Создаем экземпляр настроек
settings = Settings()


# Дополнительные утилиты для работы с настройками
def get_cors_origins() -> List[str]:
    """Получение списка разрешенных origins для CORS"""
    if isinstance(settings.ALLOWED_ORIGINS, str):
        # Если origins переданы как строка, разбиваем её
        return [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",")]
    return settings.ALLOWED_ORIGINS


def get_log_config() -> dict:
    """Получение конфигурации логирования"""
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": settings.LOG_LEVEL,
                "formatter": "default",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "": {  # Root logger
                "level": settings.LOG_LEVEL,
                "handlers": ["console"],
            },
            "garmin_service": {
                "level": settings.LOG_LEVEL,
                "handlers": ["console"],
                "propagate": False,
            },
        },
    }
    
    # Добавляем файловый логгер если указан путь к файлу
    if settings.LOG_FILE:
        config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": settings.LOG_LEVEL,
            "formatter": "detailed",
            "filename": settings.LOG_FILE,
            "maxBytes": settings.LOG_MAX_SIZE,
            "backupCount": settings.LOG_BACKUP_COUNT,
        }
        
        # Добавляем файловый обработчик к логгерам
        for logger_name in ["", "garmin_service"]:
            config["loggers"][logger_name]["handlers"].append("file")
    
    return config

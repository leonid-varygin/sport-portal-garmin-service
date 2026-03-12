from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Настройки сервиса
    service_name: str = "garmin-service"
    debug: bool = False
    
    # CORS настройки
    allowed_origins: str = '["http://localhost:3000", "http://localhost:8080"]'
    
    # Настройки для подключения к основному бэкенду
    backend_url: str = "http://host.docker.internal:3001/api"  # URL основного бэкенда (с префиксом /api)
    
    # Настройки безопасности
    secret_key: str = "your-secret-key-change-in-production"
    
    # API Key для авторизации запросов к основному бэкенду
    service_api_key: str = "garmin-service-secret-key"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

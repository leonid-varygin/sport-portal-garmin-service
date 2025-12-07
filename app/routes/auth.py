import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import asyncio

from ..services.auth_service import AuthService
from ..models.garmin_models import (
    GarminAuthRequest,
    GarminAuthResponse,
    TokenValidationResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    LogoutResponse,
    HealthCheckResponse
)
from ..config import settings

logger = logging.getLogger(__name__)

# Создаем роутер
router = APIRouter(prefix="/auth", tags=["authentication"])

# Сервис авторизации
auth_service = AuthService()

# Безопасность для Bearer токенов
security = HTTPBearer()

# API ключ для защиты эндпоинтов
API_KEY = settings.API_KEY


async def verify_api_key(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Проверка API ключа"""
    if credentials and credentials.credentials == API_KEY:
        return credentials
    raise HTTPException(
        status_code=401,
        detail="Invalid API key",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/login", response_model=GarminAuthResponse)
async def login(
    auth_request: GarminAuthRequest,
    api_key: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Аутентификация пользователя Garmin
    
    Args:
        auth_request: Данные для входа (username, password)
        api_key: API ключ для доступа к сервису
        
    Returns:
        GarminAuthResponse: Результат аутентификации с токенами
    """
    try:
        logger.info(f"Login attempt for user: {auth_request.username}")
        result = await auth_service.authenticate(auth_request)
        
        if not result.success:
            raise HTTPException(
                status_code=401,
                detail=result.error or "Authentication failed"
            )
        
        logger.info(f"Login successful for user: {auth_request.username}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error during login: {str(e)}"
        )


@router.get("/verify", response_model=TokenValidationResponse)
async def verify_token(
    token: str = Query(..., description="Токен для валидации"),
    api_key: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Валидация токена доступа
    
    Args:
        token: Токен для проверки
        api_key: API ключ для доступа к сервису
        
    Returns:
        TokenValidationResponse: Результат валидации
    """
    try:
        logger.debug(f"Token verification request: {token[:10]}...")
        result = await auth_service.validate_token(token)
        return result
        
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error during token verification: {str(e)}"
        )


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(
    refresh_request: RefreshTokenRequest,
    api_key: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Обновление токена доступа
    
    Args:
        refresh_request: Данные для обновления токена
        api_key: API ключ для доступа к сервису
        
    Returns:
        RefreshTokenResponse: Новые токены
    """
    try:
        logger.info("Token refresh request")
        result = await auth_service.refresh_token(refresh_request)
        
        if not result.success:
            raise HTTPException(
                status_code=401,
                detail=result.error or "Token refresh failed"
            )
        
        logger.info("Token refresh successful")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error during token refresh: {str(e)}"
        )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    token: str = Query(..., description="Токен для выхода"),
    api_key: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Выход из системы
    
    Args:
        token: Токен для аннулирования
        api_key: API ключ для доступа к сервису
        
    Returns:
        LogoutResponse: Результат выхода
    """
    try:
        logger.info(f"Logout request for token: {token[:10]}...")
        result = await auth_service.logout(token)
        return result
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error during logout: {str(e)}"
        )


@router.post("/cleanup")
async def cleanup_expired_sessions(
    api_key: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Очистка истекших сессий (для внутреннего использования)
    
    Args:
        api_key: API ключ для доступа к сервису
        
    Returns:
        Dict[str, int]: Результат очистки
    """
    try:
        logger.info("Cleaning up expired sessions")
        
        # Получаем количество активных сессий до очистки
        before_count = len(auth_service.active_sessions)
        
        # Выполняем очистку
        auth_service.cleanup_expired_sessions()
        
        # Получаем количество активных сессий после очистки
        after_count = len(auth_service.active_sessions)
        cleaned_count = before_count - after_count
        
        logger.info(f"Cleaned up {cleaned_count} expired sessions")
        
        return {
            "cleaned_sessions": cleaned_count,
            "active_sessions": after_count
        }
        
    except Exception as e:
        logger.error(f"Session cleanup error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error during session cleanup: {str(e)}"
        )


@router.get("/status", response_model=dict)
async def get_auth_status(
    api_key: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Получение статуса сервиса авторизации
    
    Args:
        api_key: API ключ для доступа к сервису
        
    Returns:
        Dict: Статус сервиса
    """
    try:
        return {
            "status": "healthy",
            "active_sessions": len(auth_service.active_sessions),
            "service": "garmin-auth-service",
            "version": "1.0.0"
        }
        
    except Exception as e:
        logger.error(f"Status check error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error during status check: {str(e)}"
        )


# Фоновая задача для очистки истекших сессий
async def background_cleanup():
    """Фоновая задача для периодической очистки сессий"""
    while True:
        try:
            await asyncio.sleep(300)  # Каждые 5 минут
            auth_service.cleanup_expired_sessions()
            logger.debug("Background cleanup completed")
        except Exception as e:
            logger.error(f"Background cleanup error: {str(e)}")


# Запуск фоновой задачи при старте приложения
def start_background_tasks():
    """Запуск фоновых задач"""
    import asyncio
    
    # Создаем задачу для фоновой очистки
    loop = asyncio.get_event_loop()
    loop.create_task(background_cleanup())
    logger.info("Background cleanup task started")

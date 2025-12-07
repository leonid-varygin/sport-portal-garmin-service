from fastapi import APIRouter, Depends, HTTPException
from fastapi.requests import Request
from typing import Dict, Any

from app.models.garmin_models import (
    GarminAuthRequest,
    GarminAuthResponse,
    GarminConnectionStatus
)
from app.services.garmin_service import GarminService

router = APIRouter()


def get_garmin_service(request: Request) -> GarminService:
    """Получение экземпляра GarminService из приложения"""
    return request.app.state.garmin_service


@router.post("/authenticate", response_model=GarminAuthResponse)
async def authenticate_garmin(
    auth_request: GarminAuthRequest,
    garmin_service: GarminService = Depends(get_garmin_service)
):
    """
    Аутентификация пользователя в Garmin Connect
    
    Args:
        auth_request: Данные для авторизации
        garmin_service: Сервис Garmin
        
    Returns:
        GarminAuthResponse: Результат авторизации
    """
    try:
        result = await garmin_service.authenticate(auth_request)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка авторизации в Garmin: {str(e)}"
        )


@router.get("/status/{user_id}", response_model=GarminConnectionStatus)
async def get_connection_status(
    user_id: int,
    garmin_service: GarminService = Depends(get_garmin_service)
):
    """
    Получить статус подключения к Garmin
    
    Args:
        user_id: ID пользователя
        garmin_service: Сервис Garmin
        
    Returns:
        GarminConnectionStatus: Статус подключения
    """
    try:
        result = await garmin_service.get_connection_status(user_id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка проверки статуса подключения: {str(e)}"
        )


@router.delete("/disconnect/{user_id}")
async def disconnect_garmin(
    user_id: int,
    garmin_service: GarminService = Depends(get_garmin_service)
):
    """
    Отключиться от Garmin
    
    Args:
        user_id: ID пользователя
        garmin_service: Сервис Garmin
        
    Returns:
        Dict: Результат операции
    """
    try:
        success = await garmin_service.disconnect(user_id)
        return {
            "success": success,
            "message": "Успешное отключение от Garmin" if success else "Ошибка отключения"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка отключения от Garmin: {str(e)}"
        )


@router.post("/refresh/{user_id}")
async def refresh_session(
    user_id: int,
    garmin_service: GarminService = Depends(get_garmin_service)
):
    """
    Обновить сессию Garmin
    
    Args:
        user_id: ID пользователя
        garmin_service: Сервис Garmin
        
    Returns:
        Dict: Результат операции
    """
    try:
        # Проверяем статус подключения (попытка восстановить сессию)
        status = await garmin_service.get_connection_status(user_id)
        
        return {
            "success": status.connected,
            "message": "Сессия обновлена" if status.connected else "Не удалось обновить сессию",
            "status": status
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка обновления сессии: {str(e)}"
        )

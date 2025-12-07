from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.requests import Request
from datetime import datetime, timedelta
from typing import List, Optional

from app.models.garmin_models import (
    GarminActivity,
    GarminSyncResult
)
from app.services.garmin_service import GarminService

router = APIRouter()


def get_garmin_service(request: Request) -> GarminService:
    """Получение экземпляра GarminService из приложения"""
    return request.app.state.garmin_service


@router.get("/{user_id}", response_model=List[GarminActivity])
async def get_activities(
    user_id: int,
    start_date: Optional[str] = Query(None, description="Начальная дата в формате YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Конечная дата в формате YYYY-MM-DD"),
    garmin_service: GarminService = Depends(get_garmin_service)
):
    """
    Получить активности пользователя из Garmin
    
    Args:
        user_id: ID пользователя
        start_date: Начальная дата
        end_date: Конечная дата
        garmin_service: Сервис Garmin
        
    Returns:
        List[GarminActivity]: Список активностей
    """
    try:
        # Конвертируем строки в даты если указаны
        start_dt = None
        end_dt = None
        
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Неверный формат начальной даты. Используйте YYYY-MM-DD"
                )
        
        if end_date:
            try:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Неверный формат конечной даты. Используйте YYYY-MM-DD"
                )
        
        activities = await garmin_service.get_activities(user_id, start_dt, end_dt)
        return activities
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения активностей: {str(e)}"
        )


@router.post("/sync/{user_id}", response_model=GarminSyncResult)
async def sync_activities(
    user_id: int,
    garmin_service: GarminService = Depends(get_garmin_service)
):
    """
    Синхронизировать активности пользователя с основным бэкендом
    
    Args:
        user_id: ID пользователя
        garmin_service: Сервис Garmin
        
    Returns:
        GarminSyncResult: Результат синхронизации
    """
    try:
        result = await garmin_service.sync_activities(user_id)
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка синхронизации активностей: {str(e)}"
        )


@router.get("/recent/{user_id}", response_model=List[GarminActivity])
async def get_recent_activities(
    user_id: int,
    limit: int = Query(10, ge=1, le=100, description="Количество последних активностей"),
    garmin_service: GarminService = Depends(get_garmin_service)
):
    """
    Получить последние активности пользователя
    
    Args:
        user_id: ID пользователя
        limit: Количество активностей
        garmin_service: Сервис Garmin
        
    Returns:
        List[GarminActivity]: Список последних активностей
    """
    try:
        # Получаем активности за последние 30 дней
        end_date = datetime.now()
        activities = await garmin_service.get_activities(user_id)
        
        # Сортируем по дате начала (новые первые) и ограничиваем количество
        activities.sort(key=lambda x: x.start_time, reverse=True)
        return activities[:limit]
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения последних активностей: {str(e)}"
        )


@router.get("/summary/{user_id}")
async def get_activities_summary(
    user_id: int,
    days: int = Query(30, ge=1, le=365, description="Период в днях для анализа"),
    garmin_service: GarminService = Depends(get_garmin_service)
):
    """
    Получить сводную статистику по активностям
    
    Args:
        user_id: ID пользователя
        days: Период в днях
        garmin_service: Сервис Garmin
        
    Returns:
        Dict: Сводная статистика
    """
    try:
        # Получаем активности за указанный период
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        activities = await garmin_service.get_activities(user_id, start_date, end_date)
        
        # Рассчитываем статистику
        total_activities = len(activities)
        total_distance = sum(a.distance for a in activities if a.distance)
        total_duration = sum(a.duration for a in activities if a.duration)
        total_calories = sum(a.calories for a in activities if a.calories)
        
        # Считаем по типам активностей
        activity_types = {}
        for activity in activities:
            activity_type = activity.activity_type
            if activity_type not in activity_types:
                activity_types[activity_type] = {
                    "count": 0,
                    "distance": 0,
                    "duration": 0,
                    "calories": 0
                }
            
            activity_types[activity_type]["count"] += 1
            if activity.distance:
                activity_types[activity_type]["distance"] += activity.distance
            if activity.duration:
                activity_types[activity_type]["duration"] += activity.duration
            if activity.calories:
                activity_types[activity_type]["calories"] += activity.calories
        
        return {
            "period_days": days,
            "total_activities": total_activities,
            "total_distance_km": round(total_distance / 1000, 2) if total_distance else 0,
            "total_duration_hours": round(total_duration / 3600, 2) if total_duration else 0,
            "total_calories": total_calories,
            "activity_types": activity_types,
            "last_activity_date": activities[0].start_time.isoformat() if activities else None
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения сводной статистики: {str(e)}"
        )

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.requests import Request
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import asyncio

from app.services.garmin_service import GarminService
from app.routes.garmin_health_data import GarminHealthDataAPI

router = APIRouter()


def get_garmin_service(request: Request) -> GarminService:
    """Получение экземпляра GarminService из приложения"""
    return request.app.state.garmin_service


class DailyStepsResponse:
    def __init__(self, date: str, steps: int):
        self.date = date
        self.steps = steps


@router.get("/{user_id}", response_model=List[dict])
async def get_daily_steps(
    user_id: int,
    start_date: Optional[str] = Query(None, description="Начальная дата в формате YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Конечная дата в формате YYYY-MM-DD"),
    garmin_service: GarminService = Depends(get_garmin_service)
):
    """
    Получить данные о шагах пользователя из Garmin
    
    Args:
        user_id: ID пользователя
        start_date: Начальная дата
        end_date: Конечная дата
        garmin_service: Сервис Garmin
        
    Returns:
        List[dict]: Список данных о шагах по дням
    """
    try:
        # Убедимся что сессия активна и валидна
        garmin_client = await garmin_service._ensure_valid_session(user_id)
        if not garmin_client:
            raise HTTPException(
                status_code=401,
                detail="Нет активного подключения к Garmin. Необходимо выполнить авторизацию."
            )
        
        # Устанавливаем даты по умолчанию если не указаны
        if not start_date:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        
        # Конвертируем строки в даты
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Используем новый API для получения данных
        health_api = GarminHealthDataAPI(garmin_client)
        steps_data = []
        
        current_date = start_dt
        while current_date <= end_dt:
            date_str = current_date.strftime("%Y-%m-%d")
            
            try:
                daily_data = await health_api.get_daily_health_data(date_str)
                steps_metric = daily_data["metrics"].get("Steps", {})
                
                # Извлекаем количество шагов из строки
                steps = 0
                if isinstance(steps_metric, str) and "шагов" in steps_metric:
                    steps_str = steps_metric.replace(" ", "").replace("шагов", "")
                    try:
                        steps = int(steps_str)
                    except ValueError:
                        steps = 0
                elif isinstance(steps_metric, dict):
                    steps = 0
                
                steps_data.append({
                    'date': date_str,
                    'steps': steps
                })
                    
            except Exception:
                steps_data.append({
                    'date': date_str,
                    'steps': 0
                })
            
            current_date += timedelta(days=1)
        
        return steps_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения данных о шагах: {str(e)}"
        )


@router.get("/summary/{user_id}")
async def get_steps_summary(
    user_id: int,
    days: int = Query(7, ge=1, le=365, description="Период в днях для анализа"),
    garmin_service: GarminService = Depends(get_garmin_service)
):
    """
    Получить сводную статистику по шагам
    
    Args:
        user_id: ID пользователя
        days: Период в днях
        garmin_service: Сервис Garmin
        
    Returns:
        Dict: Сводная статистика
    """
    try:
        # Убедимся что сессия активна и валидна
        garmin_client = await garmin_service._ensure_valid_session(user_id)
        if not garmin_client:
            raise HTTPException(
                status_code=401,
                detail="Нет активного подключения к Garmin. Необходимо выполнить авторизацию."
            )
        
        # Получаем данные за указанный период
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days-1)
        
        health_api = GarminHealthDataAPI(garmin_client)
        total_steps = 0
        days_with_data = 0
        daily_data = []
        
        current_date = start_date
        while current_date <= end_date:
            try:
                date_str = current_date.strftime("%Y-%m-%d")
                daily_health_data = await health_api.get_daily_health_data(date_str)
                steps_metric = daily_health_data["metrics"].get("Steps", {})
                
                # Извлекаем количество шагов из строки
                steps = 0
                if isinstance(steps_metric, str) and "шагов" in steps_metric:
                    steps_str = steps_metric.replace(" ", "").replace("шагов", "")
                    try:
                        steps = int(steps_str)
                    except ValueError:
                        steps = 0
                elif isinstance(steps_metric, dict):
                    steps = 0
                
                total_steps += steps
                if steps > 0:
                    days_with_data += 1
                
                daily_data.append({
                    'date': date_str,
                    'steps': steps
                })
                    
            except Exception:
                daily_data.append({
                    'date': current_date.strftime("%Y-%m-%d"),
                    'steps': 0
                })
            
            current_date += timedelta(days=1)
        
        average_steps = total_steps / days_with_data if days_with_data > 0 else 0
        
        return {
            "period_days": days,
            "total_steps": total_steps,
            "average_steps": round(average_steps, 1),
            "days_with_data": days_with_data,
            "daily_data": daily_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения сводной статистики: {str(e)}"
        )

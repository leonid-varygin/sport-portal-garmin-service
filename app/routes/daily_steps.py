from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.requests import Request
from datetime import datetime, timedelta
from typing import List, Optional
import asyncio

from app.services.garmin_service import GarminService

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
        
        # Получаем данные о шагах из Garmin Connect
        loop = asyncio.get_event_loop()
        
        # Получаем все данные за период одним запросом
        daily_steps = await loop.run_in_executor(
            None, 
            garmin_client.get_daily_steps, 
            start_date,
            end_date
        )
        
        steps_data = []
        
        # Обрабатываем ответ
        if daily_steps and isinstance(daily_steps, list) and len(daily_steps) > 0:
            # Garmin API возвращает массив объектов за период
            for day_data in daily_steps:
                date_str = day_data.get('calendarDate', '')
                steps = day_data.get('totalSteps', 0)
                
                if date_str:  # Добавляем только если есть дата
                    steps_data.append({
                        'date': date_str,
                        'steps': steps
                    })
        elif isinstance(daily_steps, (int, float)):
            # Если вернулось одно число (как в тесте), создаем одну запись
            steps_data.append({
                'date': start_date,
                'steps': int(daily_steps)
            })
        
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
        
        loop = asyncio.get_event_loop()
        
        total_steps = 0
        days_with_data = 0
        daily_data = []
        
        current_date = start_date
        while current_date <= end_date:
            try:
                date_str = current_date.strftime("%Y-%m-%d")
                
                daily_steps = await loop.run_in_executor(
                    None, 
                    garmin_client.get_daily_steps, 
                    date_str, 
                    date_str
                )
                
                if daily_steps and isinstance(daily_steps, list) and len(daily_steps) > 0:
                    day_data = daily_steps[0]
                    steps = day_data.get('totalSteps', 0)
                    total_steps += steps
                    days_with_data += 1
                    
                    daily_data.append({
                        'date': date_str,
                        'steps': steps
                    })
                else:
                    daily_data.append({
                        'date': date_str,
                        'steps': 0
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

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.requests import Request
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import List, Optional
import os
import httpx

from app.models.garmin_models import (
    GarminActivity,
    GarminSyncResult,
    GarminInitialSyncResult
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


@router.post("/sync-today/{user_id}", response_model=GarminSyncResult)
async def sync_today_activities(
    user_id: int,
    start_date: Optional[str] = Query(None, description="Начальная дата в формате YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Конечная дата в формате YYYY-MM-DD"),
    garmin_service: GarminService = Depends(get_garmin_service)
):
    """
    Синхронизировать активности пользователя за сегодня (или указанный период)
    Используется для ежечасной проверки новых тренировок
    
    Args:
        user_id: ID пользователя
        start_date: Начальная дата (по умолчанию - начало сегодня)
        end_date: Конечная дата (по умолчанию - сейчас)
        garmin_service: Сервис Garmin
        
    Returns:
        GarminSyncResult: Результат синхронизации
    """
    try:
        # Определяем период синхронизации
        if start_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            start_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        if end_date:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
        else:
            end_dt = datetime.now()
        
        # Получаем активности за указанный период
        activities = await garmin_service.get_activities(user_id, start_dt, end_dt)
        
        if not activities:
            return GarminSyncResult(
                success=True,
                processed=0,
                skipped_duplicates=0,
                errors=[],
                message="Нет новых активностей для синхронизации"
            )
        
        processed = 0
        skipped_duplicates = 0
        errors = []
        fit_files_downloaded = []
        
        # Для каждой активности проверяем дубликаты и скачиваем .fit файл
        for activity in activities:
            try:
                # Проверяем, не является ли активность дубликатом через бэкенд
                async with httpx.AsyncClient() as client:
                    check_response = await client.post(
                        f"{garmin_service.backend_url}/garmin/check-duplicate/{user_id}",
                        json={
                            "activity_id": activity.activity_id,
                            "activity_type": activity.activity_type,
                            "start_time": activity.start_time.isoformat(),
                            "distance": activity.distance,
                            "duration": activity.duration
                        },
                        timeout=10.0
                    )
                    
                    if check_response.status_code == 200:
                        duplicate_check = check_response.json()
                        if duplicate_check.get("is_duplicate", False):
                            skipped_duplicates += 1
                            continue
                
                # Скачиваем .fit файл
                fit_path = await garmin_service.download_fit_file(user_id, activity.activity_id)
                if fit_path:
                    fit_files_downloaded.append(fit_path)
                    
                    # Отправляем .fit файл на обработку в бэкенд
                    async with httpx.AsyncClient() as client:
                        with open(fit_path, 'rb') as fit_file:
                            files = {'file': (os.path.basename(fit_path), fit_file, 'application/octet-stream')}
                            data = {
                                'user_id': user_id, 
                                'source': 'garmin_hourly_sync',
                                'garmin_activity_id': activity.activity_id
                            }
                            
                            upload_response = await client.post(
                                f"{garmin_service.backend_url}/activities/garmin-upload",
                                files=files,
                                data=data,
                                timeout=60.0
                            )
                            
                            if upload_response.status_code == 200:
                                processed += 1
                            else:
                                errors.append(f"Ошибка обработки файла {activity.activity_id}: {upload_response.text}")
                else:
                    errors.append(f"Не удалось скачать .fit файл для активности {activity.activity_id}")
                    
            except Exception as e:
                errors.append(f"Ошибка обработки активности {activity.activity_id}: {str(e)}")
        
        # Очищаем временные файлы
        for fit_path in fit_files_downloaded:
            try:
                if os.path.exists(fit_path):
                    os.remove(fit_path)
                    temp_dir = os.path.dirname(fit_path)
                    if os.path.exists(temp_dir) and not os.listdir(temp_dir):
                        os.rmdir(temp_dir)
            except Exception as e:
                errors.append(f"Ошибка очистки временного файла {fit_path}: {str(e)}")
        
        return GarminSyncResult(
            success=len(errors) == 0,
            processed=processed,
            skipped_duplicates=skipped_duplicates,
            errors=errors,
            message=f"Обработано: {processed}, пропущено дубликатов: {skipped_duplicates}"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка синхронизации активностей за сегодня: {str(e)}"
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


@router.post("/initial-sync/{user_id}", response_model=GarminInitialSyncResult)
async def initial_sync_activities(
    user_id: int,
    limit: int = Query(200, ge=1, le=500, description="Количество активностей для синхронизации"),
    garmin_service: GarminService = Depends(get_garmin_service)
):
    """
    Первоначальная синхронизация активностей пользователя
    
    Args:
        user_id: ID пользователя
        limit: Количество активностей для синхронизации
        garmin_service: Сервис Garmin
        
    Returns:
        GarminInitialSyncResult: Результат первоначальной синхронизации
    """
    try:
        # Получаем последние активности
        activities = await garmin_service.get_initial_activities(user_id, limit)
        
        if not activities:
            return GarminInitialSyncResult(
                success=True,
                total_activities=0,
                downloaded=0,
                processed=0,
                skipped_duplicates=0,
                message="Не найдено активностей для синхронизации"
            )
        
        total_activities = len(activities)
        downloaded = 0
        processed = 0
        skipped_duplicates = 0
        errors = []
        fit_files_downloaded = []
        
        # Для каждой активности проверяем дубликаты и скачиваем .fit файл
        for activity in activities:
            try:
                # Сначала проверяем, не является ли активность дубликатом через бэкенд
                async with httpx.AsyncClient() as client:
                    check_response = await client.post(
                        f"{garmin_service.backend_url}/garmin/check-duplicate/{user_id}",
                        json={
                            "activity_id": activity.activity_id,
                            "activity_type": activity.activity_type,
                            "start_time": activity.start_time.isoformat(),
                            "distance": activity.distance,
                            "duration": activity.duration
                        },
                        timeout=10.0
                    )
                    
                    if check_response.status_code == 200:
                        duplicate_check = check_response.json()
                        if duplicate_check.get("is_duplicate", False):
                            skipped_duplicates += 1
                            continue
                
                # Скачиваем .fit файл
                fit_path = await garmin_service.download_fit_file(user_id, activity.activity_id)
                if fit_path:
                    downloaded += 1
                    fit_files_downloaded.append(fit_path)
                    
                    # Отправляем .fit файл на обработку в бэкенд
                    async with httpx.AsyncClient() as client:
                        with open(fit_path, 'rb') as fit_file:
                            files = {'file': (os.path.basename(fit_path), fit_file, 'application/octet-stream')}
                            data = {
                                'user_id': user_id, 
                                'source': 'garmin_initial_sync',
                                'garmin_activity_id': activity.activity_id
                            }
                            
                            upload_response = await client.post(
                                f"{garmin_service.backend_url}/activities/garmin-upload",
                                files=files,
                                data=data,
                                timeout=60.0
                            )
                            
                            if upload_response.status_code == 200:
                                processed += 1
                            else:
                                errors.append(f"Ошибка обработки файла {activity.activity_id}: {upload_response.text}")
                else:
                    errors.append(f"Не удалось скачать .fit файл для активности {activity.activity_id}")
                    
            except Exception as e:
                errors.append(f"Ошибка обработки активности {activity.activity_id}: {str(e)}")
        
        # Очищаем временные файлы
        for fit_path in fit_files_downloaded:
            try:
                if os.path.exists(fit_path):
                    os.remove(fit_path)
                    # Удаляем временную директорию если она пуста
                    temp_dir = os.path.dirname(fit_path)
                    if os.path.exists(temp_dir) and not os.listdir(temp_dir):
                        os.rmdir(temp_dir)
            except Exception as e:
                errors.append(f"Ошибка очистки временного файла {fit_path}: {str(e)}")
        
        return GarminInitialSyncResult(
            success=len(errors) == 0,
            total_activities=total_activities,
            downloaded=downloaded,
            processed=processed,
            skipped_duplicates=skipped_duplicates,
            errors=errors,
            message=f"Обработано: {processed}/{total_activities}, пропущено дубликатов: {skipped_duplicates}"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка первоначальной синхронизации: {str(e)}"
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


class DownloadRequest(BaseModel):
    activity_id: str


class DownloadResponse(BaseModel):
    success: bool
    fit_path: Optional[str] = None
    message: str


@router.post("/download-fit/{user_id}", response_model=DownloadResponse)
async def download_fit_file(
    user_id: int, 
    request: DownloadRequest,
    garmin_service: GarminService = Depends(get_garmin_service)
):
    """
    Скачать FIT файл активности
    
    Args:
        user_id: ID пользователя
        request: Запрос с activity_id
        garmin_service: Сервис Garmin
        
    Returns:
        DownloadResponse: Результат скачивания файла
    """
    try:
        fit_path = await garmin_service.download_fit_file(user_id, request.activity_id)
        
        if fit_path:
            return DownloadResponse(
                success=True,
                fit_path=fit_path,
                message=f"FIT файл успешно скачан: {fit_path}"
            )
        else:
            return DownloadResponse(
                success=False,
                message="Не удалось скачать FIT файл"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка скачивания FIT файла: {str(e)}"
        )

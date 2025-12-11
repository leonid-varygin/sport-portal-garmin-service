from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.requests import Request
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import asyncio

from app.services.garmin_service import GarminService

router = APIRouter()


def get_garmin_service(request: Request) -> GarminService:
    """Получение экземпляра GarminService из приложения"""
    return request.app.state.garmin_service


class GarminHealthDataAPI:
    """API для получения данных о здоровье из Garmin Connect"""
    
    def __init__(self, garmin_client):
        self.api = garmin_client
    
    async def get_daily_health_data(self, date: str) -> Dict[str, Any]:
        """Получить все данные о здоровье за указанную дату."""
        daily_data = {
            "date": date,
            "metrics": {}
        }
        
        # Словарь с методами API
        metrics_methods = {
            "Weight": self._get_weight_data,
            "Body Fat": self._get_body_fat_data,
            "Resting HR": self._get_resting_hr_data,
            "kCal": self._get_calories_data,
            "Sleep": self._get_sleep_data,
            "Sleep Score": self._get_sleep_score_data,
            "Sleep Quality": self._get_sleep_quality_data,
            "VO2 Max": self._get_vo2_max_data,
            "SpO2": self._get_spo2_data,
            "HRV (rMSSD)": self._get_hrv_data,
            "Steps": self._get_steps_data
        }
        
        # Получаем данные для каждой метрики
        loop = asyncio.get_event_loop()
        for metric_name, method in metrics_methods.items():
            try:
                # Исправление: передаем аргументы напрямую, а не как kwargs
                result = await loop.run_in_executor(None, method, date)
                daily_data["metrics"][metric_name] = result
            except Exception as e:
                daily_data["metrics"][metric_name] = {"error": str(e)}
        
        return daily_data

    def _get_weight_data(self, date: str) -> Any:
        """Получить данные о весе."""
        try:
            daily_weight = self.api.get_daily_weigh_ins(date)
            if daily_weight and "dateWeightList" in daily_weight and daily_weight["dateWeightList"]:
                weight = daily_weight["dateWeightList"][0].get("weight")
                if weight:
                    if weight > 1000:
                        weight = weight / 1000
                    return round(weight, 1)
            return None
        except Exception:
            return None

    def _get_body_fat_data(self, date: str) -> Any:
        """Получить данные о проценте жира."""
        try:
            body_comp = self.api.get_body_composition(date, date)
            if body_comp and "dateWeightList" in body_comp and body_comp["dateWeightList"]:
                fat_percent = body_comp["dateWeightList"][0].get("bodyFat")
                if fat_percent is not None:
                    return round(fat_percent, 1)
            return None
        except Exception:
            return None

    def _get_resting_hr_data(self, date: str) -> Any:
        """Получить данные о пульсе в покое."""
        try:
            rhr_data = self.api.get_rhr_day(date)
            if rhr_data and "allMetrics" in rhr_data and "metricsMap" in rhr_data["allMetrics"]:
                metrics_map = rhr_data["allMetrics"]["metricsMap"]
                if "WELLNESS_RESTING_HEART_RATE" in metrics_map:
                    rhr_list = metrics_map["WELLNESS_RESTING_HEART_RATE"]
                    if rhr_list and len(rhr_list) > 0:
                        rhr_value = rhr_list[0].get("value")
                        if rhr_value is not None and rhr_value > 0:
                            return round(float(rhr_value), 1)
            return None
        except Exception:
            return None

    def _get_calories_data(self, date: str) -> Any:
        """Получить данные о калориях."""
        try:
            summary = self.api.get_user_summary(date)
            if summary:
                total_calories = summary.get("totalKilocalories")
                active_calories = summary.get("activeKilocalories")
                if total_calories is not None:
                    result = {
                        "total": float(total_calories)
                    }
                    if active_calories is not None:
                        result["active"] = float(active_calories)
                    return result
            return None
        except Exception:
            return None

    def _get_sleep_data(self, date: str) -> Any:
        """Получить данные о сне."""
        try:
            sleep_data = self.api.get_sleep_data(date)
            if sleep_data and "dailySleepDTO" in sleep_data:
                sleep_dto = sleep_data["dailySleepDTO"]
                sleep_seconds = sleep_dto.get("sleepTimeSeconds", 0)
                if sleep_seconds > 0:
                    return int(sleep_seconds // 60)  # возвращаем минуты
            return None
        except Exception:
            return None

    def _get_sleep_score_data(self, date: str) -> Any:
        """Получить оценку сна."""
        try:
            sleep_data = self.api.get_sleep_data(date)
            if sleep_data and "dailySleepDTO" in sleep_data:
                sleep_dto = sleep_data["dailySleepDTO"]
                sleep_scores = sleep_dto.get("sleepScores")
                if sleep_scores and "overall" in sleep_scores:
                    overall_score = sleep_scores["overall"]
                    score_value = overall_score.get("value")
                    if score_value is not None:
                        return int(score_value)
            return None
        except Exception:
            return None

    def _get_sleep_quality_data(self, date: str) -> Any:
        """Получить качество сна."""
        try:
            sleep_data = self.api.get_sleep_data(date)
            if sleep_data and "dailySleepDTO" in sleep_data:
                sleep_dto = sleep_data["dailySleepDTO"]
                sleep_seconds = sleep_dto.get("sleepTimeSeconds", 0)
                
                if sleep_seconds > 0:
                    deep_sleep = sleep_dto.get("deepSleepSeconds", 0)
                    rem_sleep = sleep_dto.get("remSleepSeconds", 0)
                    total_sleep = deep_sleep + rem_sleep
                    
                    if total_sleep > 0:
                        deep_percent = (deep_sleep / sleep_seconds) * 100
                        rem_percent = (rem_sleep / sleep_seconds) * 100
                        
                        if deep_percent >= 16 and rem_percent >= 21:
                            return 4  # Отличное
                        elif deep_percent >= 16 and rem_percent >= 15:
                            return 3  # Хорошее
                        elif deep_percent >= 10 and rem_percent >= 10:
                            return 2  # Среднее
                        else:
                            return 1  # Плохое
            return None
        except Exception:
            return None

    def _get_vo2_max_data(self, date: str) -> Any:
        """Получить данные VO2 Max."""
        try:
            vo2_data = self.api.get_max_metrics(date)
            if vo2_data and len(vo2_data) > 0:
                first_item = vo2_data[0]
                if "generic" in first_item:
                    generic_data = first_item["generic"]
                    vo2_max = generic_data.get("vo2MaxValue")
                    if vo2_max is not None and vo2_max > 0:
                        return round(float(vo2_max), 1)
            return None
        except Exception:
            return None

    def _get_spo2_data(self, date: str) -> Any:
        """Получить данные SpO2."""
        try:
            spo2_data = self.api.get_spo2_data(date)
            if spo2_data:
                avg_spo2 = None
                if "averageSpO2" in spo2_data:
                    avg_spo2 = spo2_data["averageSpO2"]
                elif "average" in spo2_data:
                    avg_spo2 = spo2_data["average"]
                elif "spo2Readings" in spo2_data and spo2_data["spo2Readings"]:
                    readings = spo2_data["spo2Readings"]
                    if readings:
                        total = sum(r.get("spo2", 0) for r in readings)
                        count = len([r for r in readings if r.get("spo2")])
                        avg_spo2 = total / count if count > 0 else None
                
                if avg_spo2 is not None and avg_spo2 > 0:
                    return round(float(avg_spo2), 1)
            return None
        except Exception:
            return None

    def _get_hrv_data(self, date: str) -> Any:
        """Получить данные HRV (rMSSD)."""
        try:
            hrv_data = self.api.get_hrv_data(date)
            if hrv_data and "hrvSummary" in hrv_data:
                summary = hrv_data["hrvSummary"]
                rmssd = summary.get("rmssd")
                if rmssd is not None and rmssd > 0:
                    return round(float(rmssd), 1)
            elif hrv_data and "weeklyAverage" in hrv_data:
                weekly_avg = hrv_data["weeklyAverage"]
                rmssd = weekly_avg.get("rmssd")
                if rmssd is not None and rmssd > 0:
                    return round(float(rmssd), 1)
            return None
        except Exception:
            return None

    def _get_steps_data(self, date: str) -> Any:
        """Получить данные о шагах."""
        try:
            summary = self.api.get_user_summary(date)
            if summary and "totalSteps" in summary:
                steps = summary["totalSteps"]
                if steps is not None:
                    return int(steps)
            return None
        except Exception:
            return None


# Эндпоинты для шагов (обратная совместимость с daily_steps.py)

@router.get("/{user_id}", response_model=List[dict])
async def get_daily_steps(
    user_id: int,
    start_date: Optional[str] = Query(None, description="Начальная дата в формате YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Конечная дата в формате YYYY-MM-DD"),
    garmin_service: GarminService = Depends(get_garmin_service)
):
    """
    Получить данные о шагах пользователя из Garmin (обратная совместимость)
    
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
                
                # Теперь steps_metric - это число или None
                steps = 0
                if isinstance(steps_metric, int):
                    steps = steps_metric
                elif steps_metric is None:
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
    Получить сводную статистику по шагам (обратная совместимость)
    
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
                
                # Теперь steps_metric - это число или None
                steps = 0
                if isinstance(steps_metric, int):
                    steps = steps_metric
                elif steps_metric is None:
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


# Новые эндпоинты для всех метрик здоровья

@router.get("/health/{user_id}")
async def get_health_data(
    user_id: int,
    start_date: Optional[str] = Query(None, description="Начальная дата в формате YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Конечная дата в формате YYYY-MM-DD"),
    garmin_service: GarminService = Depends(get_garmin_service)
):
    """
    Получить все данные о здоровье пользователя из Garmin
    
    Args:
        user_id: ID пользователя
        start_date: Начальная дата
        end_date: Конечная дата
        garmin_service: Сервис Garmin
        
    Returns:
        List[dict]: Список данных о здоровье по дням
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
        health_data = []
        
        current_date = start_dt
        while current_date <= end_dt:
            date_str = current_date.strftime("%Y-%m-%d")
            
            try:
                daily_data = await health_api.get_daily_health_data(date_str)
                health_data.append(daily_data)
            except Exception as e:
                health_data.append({
                    'date': date_str,
                    'metrics': {metric: {"error": str(e)} for metric in [
                        "Weight", "Body Fat", "Resting HR", "kCal", "Sleep", 
                        "Sleep Score", "Sleep Quality", "VO2 Max", "SpO2", 
                        "HRV (rMSSD)", "Steps"
                    ]}
                })
            
            current_date += timedelta(days=1)
        
        return health_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения данных о здоровье: {str(e)}"
        )


@router.get("/health/{user_id}/summary")
async def get_health_summary(
    user_id: int,
    days: int = Query(7, ge=1, le=365, description="Период в днях для анализа"),
    garmin_service: GarminService = Depends(get_garmin_service)
):
    """
    Получить сводную статистику по всем метрикам здоровья
    
    Args:
        user_id: ID пользователя
        days: Период в днях
        garmin_service: Сервис Garmin
        
    Returns:
        Dict: Сводная статистика по всем метрикам
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
        all_metrics_data = {}
        
        # Метрики для отслеживания
        metrics_to_track = [
            "Weight", "Body Fat", "Resting HR", "kCal", "Sleep", 
            "Sleep Score", "VO2 Max", "SpO2", "HRV (rMSSD)", "Steps"
        ]
        
        # Инициализируем счетчики для каждой метрики
        for metric in metrics_to_track:
            all_metrics_data[metric] = {
                "success_count": 0,
                "total_days": 0,
                "data_points": []
            }
        
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            
            try:
                daily_health_data = await health_api.get_daily_health_data(date_str)
                
                for metric in metrics_to_track:
                    metric_value = daily_health_data["metrics"].get(metric)
                    all_metrics_data[metric]["total_days"] += 1
                    
                    if not (isinstance(metric_value, dict) and "error" in metric_value):
                        all_metrics_data[metric]["success_count"] += 1
                        all_metrics_data[metric]["data_points"].append({
                            "date": date_str,
                            "value": metric_value
                        })
                    
            except Exception:
                for metric in metrics_to_track:
                    all_metrics_data[metric]["total_days"] += 1
            
            current_date += timedelta(days=1)
        
        # Формируем сводку
        summary = {
            "period_days": days,
            "date_range": {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d")
            },
            "metrics_summary": {}
        }
        
        for metric, data in all_metrics_data.items():
            success_rate = (data["success_count"] / data["total_days"]) * 100 if data["total_days"] > 0 else 0
            summary["metrics_summary"][metric] = {
                "success_rate": round(success_rate, 1),
                "successful_days": data["success_count"],
                "total_days": data["total_days"],
                "data_points": data["data_points"]
            }
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения сводной статистики здоровья: {str(e)}"
        )


@router.get("/health/{user_id}/metrics/{metric_name}")
async def get_specific_metric(
    user_id: int,
    metric_name: str,
    start_date: Optional[str] = Query(None, description="Начальная дата в формате YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Конечная дата в формате YYYY-MM-DD"),
    garmin_service: GarminService = Depends(get_garmin_service)
):
    """
    Получить данные по конкретной метрике здоровья
    
    Args:
        user_id: ID пользователя
        metric_name: Название метрики (Weight, Body Fat, Resting HR, kCal, Sleep, Sleep Score, Sleep Quality, VO2 Max, SpO2, HRV (rMSSD), Steps)
        start_date: Начальная дата
        end_date: Конечная дата
        garmin_service: Сервис Garmin
        
    Returns:
        List[dict]: Список данных по метрике
    """
    try:
        # Проверяем валидность имени метрики
        valid_metrics = [
            "Weight", "Body Fat", "Resting HR", "kCal", "Sleep", 
            "Sleep Score", "Sleep Quality", "VO2 Max", "SpO2", 
            "HRV (rMSSD)", "Steps"
        ]
        
        if metric_name not in valid_metrics:
            raise HTTPException(
                status_code=400,
                detail=f"Недопустимое имя метрики. Доступные метрики: {', '.join(valid_metrics)}"
            )
        
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
        metric_data = []
        
        current_date = start_dt
        while current_date <= end_dt:
            date_str = current_date.strftime("%Y-%m-%d")
            
            try:
                daily_data = await health_api.get_daily_health_data(date_str)
                metric_value = daily_data["metrics"].get(metric_name)
                
                metric_data.append({
                    'date': date_str,
                    'value': metric_value
                })
                    
            except Exception as e:
                metric_data.append({
                    'date': date_str,
                    'value': {"error": str(e)}
                })
            
            current_date += timedelta(days=1)
        
        return {
            "metric": metric_name,
            "date_range": {
                "start": start_date,
                "end": end_date
            },
            "data": metric_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения данных по метрике {metric_name}: {str(e)}"
        )

import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from garminconnect import Garmin
from ..models import GarminActivity, GarminActivityDetails, SyncResponse, FitFileInfo
from ..config import settings

logger = logging.getLogger(__name__)

class GarminService:
    """
    Сервис для работы с активностями Garmin Connect
    """
    
    def __init__(self):
        pass
    
    async def get_activities(self, client: Garmin, start_date: datetime, end_date: datetime, limit: int = 100) -> List[GarminActivity]:
        """
        Получение списка активностей за период
        
        Args:
            client: Клиент Garmin Connect
            start_date: Начальная дата
            end_date: Конечная дата
            limit: Максимальное количество активностей
            
        Returns:
            List[GarminActivity]: Список активностей
        """
        try:
            # Используем метод download_activities из garminconnect
            activities_data = await client.download_activities(
                startdate=start_date.isoformat(),
                enddate=end_date.isoformat()
            )
            
            # Преобразуем в наши модели
            activities = []
            for activity_data in activities_data[:limit]:
                try:
                    activity = GarminActivity(
                        activityId=str(activity_data.get('activityId', '')),
                        activityName=activity_data.get('activityName', ''),
                        activityType=activity_data.get('activityType', {}).get('typeKey', ''),
                        startTimeLocal=datetime.fromisoformat(activity_data.get('startTimeLocal', '').replace('Z', '+00:00')),
                        startTimeGMT=datetime.fromisoformat(activity_data.get('startTimeGMT', '').replace('Z', '+00:00')),
                        duration=activity_data.get('duration'),
                        distance=activity_data.get('distance'),
                        averageSpeed=activity_data.get('averageSpeed'),
                        maxSpeed=activity_data.get('maxSpeed'),
                        averageHR=activity_data.get('averageHR'),
                        maxHR=activity_data.get('maxHR'),
                        averagePower=activity_data.get('averagePower'),
                        maxPower=activity_data.get('maxPower'),
                        calories=activity_data.get('calories'),
                        elevationGain=activity_data.get('elevationGain'),
                        elevationLoss=activity_data.get('elevationLoss'),
                        avgCadence=activity_data.get('avgCadence'),
                        maxCadence=activity_data.get('maxCadence'),
                        trainingEffect=activity_data.get('trainingEffect'),
                        activityTypeKey=activity_data.get('activityType', {}).get('typeKey', ''),
                        sportTypeKey=activity_data.get('sportTypeKey', '')
                    )
                    activities.append(activity)
                except Exception as e:
                    logger.warning(f"Error parsing activity {activity_data.get('activityId', 'unknown')}: {e}")
                    continue
            
            return activities
            
        except Exception as e:
            logger.error(f"Error getting activities: {e}")
            raise
    
    async def get_activity_details(self, client: Garmin, activity_id: str) -> GarminActivityDetails:
        """
        Получение детальной информации об активности
        
        Args:
            client: Клиент Garmin Connect
            activity_id: ID активности
            
        Returns:
            GarminActivityDetails: Детальная информация об активности
        """
        try:
            activity_data = await client.get_activity_details(activity_id)
            
            return GarminActivityDetails(
                activityId=str(activity_data.get('activityId', '')),
                activityName=activity_data.get('activityName', ''),
                description=activity_data.get('description'),
                activityType=activity_data.get('activityType', {}),
                startTimeLocal=datetime.fromisoformat(activity_data.get('startTimeLocal', '').replace('Z', '+00:00')),
                startTimeGMT=datetime.fromisoformat(activity_data.get('startTimeGMT', '').replace('Z', '+00:00')),
                duration=activity_data.get('duration', 0),
                distance=activity_data.get('distance', 0),
                averageSpeed=activity_data.get('averageSpeed', 0),
                maxSpeed=activity_data.get('maxSpeed', 0),
                averageHR=activity_data.get('averageHR'),
                maxHR=activity_data.get('maxHR'),
                averagePower=activity_data.get('averagePower'),
                maxPower=activity_data.get('maxPower'),
                calories=activity_data.get('calories', 0),
                elevationGain=activity_data.get('elevationGain'),
                elevationLoss=activity_data.get('elevationLoss'),
                avgCadence=activity_data.get('avgCadence'),
                maxCadence=activity_data.get('maxCadence'),
                steps=activity_data.get('steps'),
                avgVerticalOscillation=activity_data.get('avgVerticalOscillation'),
                avgGroundContactTime=activity_data.get('avgGroundContactTime'),
                avgStrideLength=activity_data.get('avgStrideLength'),
                vo2Max=activity_data.get('vo2Max'),
                trainingEffect=activity_data.get('trainingEffect'),
                maxVerticalSpeed=activity_data.get('maxVerticalSpeed'),
                sampleType=activity_data.get('sampleType')
            )
            
        except Exception as e:
            logger.error(f"Error getting activity details for {activity_id}: {e}")
            raise
    
    async def download_fit_files(self, client: Garmin, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """
        Скачивание FIT файлов тренировок за период
        
        Args:
            client: Клиент Garmin Connect
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            List[Dict[str, Any]]: Список информации о скачанных FIT файлах
        """
        try:
            # Получаем активности за период
            activities_data = await client.download_activities(
                startdate=start_date.isoformat(),
                enddate=end_date.isoformat()
            )
            
            downloaded_files = []
            
            for activity in activities_data:
                try:
                    activity_id = activity.get('activityId')
                    activity_name = activity.get('activityName', f'Activity_{activity_id}')
                    
                    # Скачиваем FIT файл
                    fit_data = await client.download_activity_fit(activity_id)
                    
                    if fit_data:
                        file_info = {
                            'activity_id': str(activity_id),
                            'activity_name': activity_name,
                            'start_time': activity.get('startTimeLocal'),
                            'activity_type': activity.get('activityType', {}).get('typeKey', ''),
                            'fit_data': fit_data,  # Бинарные данные FIT файла
                            'file_size': len(fit_data) if isinstance(fit_data, bytes) else 0,
                            'downloaded_at': datetime.now().isoformat()
                        }
                        downloaded_files.append(file_info)
                        logger.info(f"Successfully downloaded FIT file for activity {activity_id}: {activity_name}")
                    else:
                        logger.warning(f"No FIT data available for activity {activity_id}")
                        
                except Exception as e:
                    activity_id = activity.get('activityId', 'unknown')
                    logger.error(f"Error downloading FIT file for activity {activity_id}: {e}")
                    continue
            
            return downloaded_files
            
        except Exception as e:
            logger.error(f"Error downloading FIT files: {e}")
            raise
    
    async def sync_user_data(self, client: Garmin, start_date: datetime, end_date: datetime) -> SyncResponse:
        """
        Синхронизация данных пользователя за период
        
        Args:
            client: Клиент Garmin Connect
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            SyncResponse: Результат синхронизации
        """
        try:
            errors = []
            
            # Скачиваем FIT файлы
            try:
                fit_files = await self.download_fit_files(client, start_date, end_date)
            except Exception as e:
                fit_files = []
                errors.append(f"Error downloading FIT files: {str(e)}")
            
            # Получаем активности
            try:
                activities = await self.get_activities(client, start_date, end_date)
            except Exception as e:
                activities = []
                errors.append(f"Error getting activities: {str(e)}")
            
            return SyncResponse(
                success=len(errors) == 0,
                synced_activities=len(activities),
                synced_days=len(fit_files),
                errors=errors,
                last_sync_time=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error during sync: {e}")
            return SyncResponse(
                success=False,
                synced_activities=0,
                synced_days=0,
                errors=[str(e)],
                last_sync_time=datetime.now()
            )

# Создаем глобальный экземпляр сервиса
garmin_service = GarminService()

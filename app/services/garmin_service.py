import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import httpx

from garminconnect import Garmin

from app.config import settings
from app.models.garmin_models import (
    GarminAuthRequest,
    GarminAuthResponse,
    GarminConnectionStatus,
    GarminActivity,
    GarminSyncResult,
    GarminAuthStatus,
    GarminError
)

logger = logging.getLogger(__name__)


class GarminService:
    """Сервис для работы с Garmin Connect"""
    
    def __init__(self):
        self.active_sessions: Dict[int, Garmin] = {}  # user_id -> Garmin client
        self.session_cache: Dict[int, Dict[str, Any]] = {}  # Кеш сессий
        
    async def authenticate(self, auth_request: GarminAuthRequest) -> GarminAuthResponse:
        """
        Аутентификация пользователя в Garmin Connect
        
        Args:
            auth_request: Данные для авторизации
            
        Returns:
            GarminAuthResponse: Результат авторизации
        """
        try:
            # Создаем клиент Garmin
            garmin_client = Garmin(auth_request.username, auth_request.password)
            
            # Выполняем вход (синхронный вызов в asyncio)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, garmin_client.login)
            
            # Получаем информацию о пользователе
            user_info = await loop.run_in_executor(None, garmin_client.get_user_profile)
            
            # Сохраняем сессию
            self.active_sessions[auth_request.user_id] = garmin_client
            
            # Кешируем информацию о сессии
            self.session_cache[auth_request.user_id] = {
                'username': auth_request.username,
                'password': auth_request.password,
                'garmin_user_id': str(user_info.get('displayName', '')),
                'display_name': user_info.get('displayName', ''),
                'created_at': datetime.now(),
                'last_used': datetime.now()
            }
            
            # Отправляем токены в основной бэкенд для сохранения
            await self._save_tokens_to_backend(
                auth_request.user_id,
                auth_request.username,
                auth_request.password,
                user_info
            )
            
            return GarminAuthResponse(
                success=True,
                status=GarminAuthStatus.CONNECTED,
                message="Успешная авторизация в Garmin Connect",
                garmin_user_id=str(user_info.get('displayName', '')),
                display_name=user_info.get('displayName', '')
            )
            
        except Exception as e:
            logger.error(f"Garmin authentication failed for user {auth_request.user_id}: {str(e)}")
            
            # Очищаем сессию в случае ошибки
            if auth_request.user_id in self.active_sessions:
                del self.active_sessions[auth_request.user_id]
            if auth_request.user_id in self.session_cache:
                del self.session_cache[auth_request.user_id]
            
            error_message = self._parse_auth_error(str(e))
            
            return GarminAuthResponse(
                success=False,
                status=GarminAuthStatus.ERROR,
                message=error_message
            )
    
    async def get_connection_status(self, user_id: int) -> GarminConnectionStatus:
        """
        Получить статус подключения к Garmin
        
        Args:
            user_id: ID пользователя
            
        Returns:
            GarminConnectionStatus: Статус подключения
        """
        try:
            # Проверяем есть ли активная сессия
            if user_id not in self.active_sessions:
                # Пробуем восстановить сессию из кеша или бэкенда
                restored = await self._restore_session(user_id)
                if not restored:
                    return GarminConnectionStatus(
                        connected=False,
                        message="Нет активного подключения к Garmin"
                    )
            
            # Проверяем валидность сессии
            garmin_client = self.active_sessions[user_id]
            
            # Пробуем получить профиль пользователя для проверки сессии
            loop = asyncio.get_event_loop()
            try:
                user_info = await loop.run_in_executor(None, garmin_client.get_user_profile)
                session_info = self.session_cache.get(user_id, {})
                
                return GarminConnectionStatus(
                    connected=True,
                    garmin_user_id=str(user_info.get('displayName', '')),
                    display_name=user_info.get('displayName', ''),
                    last_sync=session_info.get('last_used'),
                    message="Подключено к Garmin Connect"
                )
            except Exception as e:
                # Сессия недействительна
                await self._cleanup_session(user_id)
                return GarminConnectionStatus(
                    connected=False,
                    message="Сессия Garmin недействительна"
                )
                
        except Exception as e:
            logger.error(f"Error checking Garmin connection status for user {user_id}: {str(e)}")
            return GarminConnectionStatus(
                connected=False,
                message=f"Ошибка проверки статуса: {str(e)}"
            )
    
    async def disconnect(self, user_id: int) -> bool:
        """
        Отключиться от Garmin
        
        Args:
            user_id: ID пользователя
            
        Returns:
            bool: Успешность отключения
        """
        try:
            await self._cleanup_session(user_id)
            
            # Уведомляем бэкенд об отключении
            await self._notify_backend_disconnection(user_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error disconnecting Garmin for user {user_id}: {str(e)}")
            return False
    
    async def get_activities(self, user_id: int, start_date: Optional[datetime] = None, 
                           end_date: Optional[datetime] = None) -> List[GarminActivity]:
        """
        Получить активности из Garmin
        
        Args:
            user_id: ID пользователя
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            List[GarminActivity]: Список активностей
        """
        try:
            # Убедимся что сессия активна и валидна
            garmin_client = await self._ensure_valid_session(user_id)
            if not garmin_client:
                raise Exception("Нет активного подключения к Garmin")
            
            loop = asyncio.get_event_loop()
            
            # Получаем активности - используем правильные параметры для garminconnect
            try:
                # Пробуем сначала без параметров
                activities_data = await loop.run_in_executor(None, garmin_client.get_activities)
            except Exception as e:
                logger.warning(f"Failed to get activities without params: {str(e)}")
                
                # Пробуем с числовыми параметрами (start, end) где start=0, end=количество дней
                try:
                    if start_date and end_date:
                        # Конвертируем даты в количество дней от начала
                        days_diff = (end_date - start_date).days
                        activities_data = await loop.run_in_executor(None, garmin_client.get_activities, 0, days_diff)
                    else:
                        # Получаем активности за последние 30 дней по умолчанию
                        activities_data = await loop.run_in_executor(None, garmin_client.get_activities, 0, 30)
                except Exception as e2:
                    logger.error(f"All attempts to get activities failed: {str(e2)}")
                    raise Exception(f"Не удалось получить активности Garmin: {str(e2)}")
            
            # Конвертируем в нашу модель
            activities = []
            for activity in activities_data:
                garmin_activity = self._convert_to_garmin_activity(activity)
                if garmin_activity:
                    activities.append(garmin_activity)
            
            # Обновляем время последнего использования сессии
            if user_id in self.session_cache:
                self.session_cache[user_id]['last_used'] = datetime.now()
            
            return activities
            
        except Exception as e:
            logger.error(f"Error getting Garmin activities for user {user_id}: {str(e)}")
            raise Exception(f"Ошибка получения активностей: {str(e)}")
    
    async def sync_activities(self, user_id: int) -> GarminSyncResult:
        """
        Синхронизировать активности с основным бэкендом
        
        Args:
            user_id: ID пользователя
            
        Returns:
            GarminSyncResult: Результат синхронизации
        """
        try:
            # Получаем активности за последние 7 дней
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            activities = await self.get_activities(user_id, start_date=start_date, end_date=end_date)
            
            synced_count = 0
            skipped_count = 0
            errors = []
            
            # Отправляем активности на основной бэкенд
            for activity in activities:
                try:
                    success = await self._send_activity_to_backend(user_id, activity)
                    if success:
                        synced_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    errors.append(f"Ошибка синхронизации активности {activity.activity_id}: {str(e)}")
            
            return GarminSyncResult(
                success=len(errors) == 0,
                synced=synced_count,
                skipped=skipped_count,
                errors=errors,
                message=f"Синхронизировано: {synced_count}, пропущено: {skipped_count}"
            )
            
        except Exception as e:
            logger.error(f"Error syncing Garmin activities for user {user_id}: {str(e)}")
            return GarminSyncResult(
                success=False,
                errors=[f"Ошибка синхронизации: {str(e)}"],
                message="Синхронизация не удалась"
            )
    
    async def _restore_session(self, user_id: int) -> bool:
        """Восстановление сессии пользователя"""
        try:
            # Получаем сохраненные токены с бэкенда
            tokens = await self._get_tokens_from_backend(user_id)
            if not tokens:
                return False
            
            # Создаем новый клиент и выполняем вход
            garmin_client = Garmin(tokens['username'], tokens['password'])
            loop = asyncio.get_event_loop()
            
            # Пробуем войти с несколькими попытками
            for attempt in range(3):
                try:
                    await loop.run_in_executor(None, garmin_client.login)
                    break
                except Exception as e:
                    if attempt == 2:
                        raise e
                    logger.warning(f"Garmin login attempt {attempt + 1} failed, retrying...")
                    await asyncio.sleep(2)
            
            # Сохраняем сессию
            self.active_sessions[user_id] = garmin_client
            self.session_cache[user_id] = {
                'username': tokens['username'],
                'password': tokens['password'],
                'garmin_user_id': tokens.get('garmin_user_id', ''),
                'display_name': tokens.get('display_name', ''),
                'created_at': datetime.now(),
                'last_used': datetime.now()
            }
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore Garmin session for user {user_id}: {str(e)}")
            return False
    
    async def _ensure_valid_session(self, user_id: int) -> Optional[Garmin]:
        """
        Убедиться что сессия пользователя активна и валидна
        Автоматически восстанавливает сессию если необходимо
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Optional[Garmin]: Валидный клиент Garmin или None
        """
        try:
            # Если сессии нет, пробуем восстановить
            if user_id not in self.active_sessions:
                restored = await self._restore_session(user_id)
                return self.active_sessions.get(user_id) if restored else None
            
            garmin_client = self.active_sessions[user_id]
            
            # Проверяем валидность сессии пробуя получить профиль
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, garmin_client.get_user_profile)
                
                # Обновляем время последнего использования
                if user_id in self.session_cache:
                    self.session_cache[user_id]['last_used'] = datetime.now()
                
                return garmin_client
                
            except Exception as e:
                logger.warning(f"Garmin session invalid for user {user_id}, attempting refresh: {str(e)}")
                
                # Сессия недействительна, пробуем восстановить
                await self._cleanup_session(user_id)
                restored = await self._restore_session(user_id)
                
                return self.active_sessions.get(user_id) if restored else None
                
        except Exception as e:
            logger.error(f"Error ensuring valid Garmin session for user {user_id}: {str(e)}")
            return None

    async def _cleanup_session(self, user_id: int):
        """Очистка сессии пользователя"""
        if user_id in self.active_sessions:
            del self.active_sessions[user_id]
        if user_id in self.session_cache:
            del self.session_cache[user_id]
    
    def _convert_to_garmin_activity(self, activity_data: Dict[str, Any]) -> Optional[GarminActivity]:
        """Конвертация данных Garmin в нашу модель"""
        try:
            return GarminActivity(
                activity_id=str(activity_data.get('activityId', '')),
                activity_name=activity_data.get('activityName', ''),
                activity_type=activity_data.get('activityType', {}).get('typeKey', ''),
                start_time=datetime.fromisoformat(activity_data.get('startTimeLocal', '').replace('Z', '+00:00')),
                end_time=datetime.fromisoformat(activity_data.get('startTimeLocal', '').replace('Z', '+00:00')) + timedelta(seconds=activity_data.get('duration', 0)),
                duration=activity_data.get('duration'),
                distance=activity_data.get('distance'),
                average_hr=activity_data.get('averageHR'),
                max_hr=activity_data.get('maxHR'),
                calories=activity_data.get('calories'),
                elevation_gain=activity_data.get('elevationGain'),
                avg_speed=activity_data.get('averageSpeed'),
                max_speed=activity_data.get('maxSpeed')
            )
        except Exception as e:
            logger.error(f"Error converting Garmin activity: {str(e)}")
            return None
    
    def _parse_auth_error(self, error_message: str) -> str:
        """Парсинг ошибки авторизации"""
        if "invalid credentials" in error_message.lower() or "authentication failed" in error_message.lower():
            return "Неверный логин или пароль Garmin Connect"
        elif "two factor" in error_message.lower() or "2fa" in error_message.lower():
            return "Требуется двухфакторная аутентификация. Пожалуйста, отключите 2FA в настройках Garmin Connect или используйте app-пароль."
        elif "account locked" in error_message.lower():
            return "Учетная запись Garmin заблокирована. Пожалуйста, обратитесь в поддержку Garmin."
        elif "connection" in error_message.lower():
            return "Ошибка подключения к серверам Garmin. Попробуйте позже."
        else:
            return f"Ошибка авторизации: {error_message}"
    
    async def _save_tokens_to_backend(self, user_id: int, username: str, password: str, user_info: Dict[str, Any]):
        """Сохранение токенов на основном бэкенде"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.backend_url}/garmin/save-tokens",
                    json={
                        "user_id": user_id,
                        "username": username,
                        "password": password,
                        "garmin_user_id": str(user_info.get('displayName', '')),
                        "display_name": user_info.get('displayName', '')
                    },
                    timeout=10.0
                )
                response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to save Garmin tokens to backend: {str(e)}")
            # Не прерываем процесс, так как это не критично для авторизации
    
    async def _get_tokens_from_backend(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получение токенов с основного бэкенда"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.backend_url}/garmin/get-tokens/{user_id}",
                    timeout=10.0
                )
                if response.status_code == 200:
                    return response.json()
                return None
        except Exception as e:
            logger.error(f"Failed to get Garmin tokens from backend: {str(e)}")
            return None
    
    async def _send_activity_to_backend(self, user_id: int, activity: GarminActivity) -> bool:
        """Отправка активности на основной бэкенд"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.backend_url}/garmin/activity",
                    json={
                        "user_id": user_id,
                        "activity": activity.dict()
                    },
                    timeout=30.0
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send Garmin activity to backend: {str(e)}")
            return False
    
    async def _notify_backend_disconnection(self, user_id: int):
        """Уведомление бэкенда об отключении"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{settings.backend_url}/garmin/disconnect/{user_id}",
                    timeout=10.0
                )
                response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to notify backend about Garmin disconnection: {str(e)}")

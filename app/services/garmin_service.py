import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import httpx
import zipfile
import tempfile
import os

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
from app.services.token_manager import TokenManager

logger = logging.getLogger(__name__)


class GarminService:
    """Сервис для работы с Garmin Connect"""
    
    def __init__(self):
        self.active_sessions: Dict[int, Garmin] = {}  # user_id -> Garmin client
        self.session_cache: Dict[int, Dict[str, Any]] = {}  # Кеш сессий
        self.backend_url = settings.backend_url
        
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
            
            # Сохраняем токены в файлы для автоматической переавторизации
            token_manager = TokenManager(auth_request.user_id)
            token_save_success = token_manager.save_tokens(garmin_client)
            if token_save_success:
                logger.info(f"Successfully saved tokens to files for user {auth_request.user_id}")
            else:
                logger.warning(f"Failed to save tokens to files for user {auth_request.user_id}")
            
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
            
            # Удаляем сохраненные токены
            token_manager = TokenManager(user_id)
            token_manager.delete_tokens()
            
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
        """Восстановление сессии пользователя с автоматической переавторизацией"""
        try:
            # Сначала пробуем восстановить из файлов токенов
            token_manager = TokenManager(user_id)
            
            if token_manager.are_tokens_valid():
                logger.info(f"Found valid tokens in files for user {user_id}, attempting token restoration")
                
                try:
                    # Пробуем создать клиент с токенами
                    garmin_client = Garmin()
                    
                    # Восстанавливаем токены в клиенте
                    if token_manager.restore_tokens_to_client(garmin_client):
                        # Проверяем валидность сессии
                        loop = asyncio.get_event_loop()
                        try:
                            user_info = await loop.run_in_executor(None, garmin_client.get_user_profile)
                            logger.info(f"Successfully restored session from tokens for user {user_id}")
                            
                            # Сохраняем сессию
                            self.active_sessions[user_id] = garmin_client
                            self.session_cache[user_id] = {
                                'username': '',  # Не храним пароль при восстановлении из токенов
                                'password': '',  # Не храним пароль при восстановлении из токенов
                                'garmin_user_id': str(user_info.get('displayName', '')),
                                'display_name': user_info.get('displayName', ''),
                                'created_at': datetime.now(),
                                'last_used': datetime.now(),
                                'restored_from_tokens': True
                            }
                            
                            return True
                            
                        except Exception as token_error:
                            logger.warning(f"Token restoration failed for user {user_id}: {str(token_error)}")
                            # Токены невалидны, удаляем их
                            token_manager.delete_tokens()
                            logger.info(f"Deleted invalid tokens for user {user_id}")
                except Exception as restore_error:
                    logger.warning(f"Failed to restore tokens for user {user_id}: {str(restore_error)}")
            
            # Если не удалось восстановить из токенов, пробуем получить данные с бэкенда
            logger.info(f"Attempting to restore session from backend for user {user_id}")
            tokens = await self._get_tokens_from_backend(user_id)
            if not tokens:
                logger.warning(f"No tokens found for user {user_id}")
                return False
            
            # Проверяем наличие обязательных полей
            if not tokens.get('username') or not tokens.get('password'):
                logger.error(f"Invalid tokens for user {user_id}: missing username or password")
                return False
            
            # Создаем новый клиент и выполняем вход с несколькими попытками
            garmin_client = Garmin(tokens['username'], tokens['password'])
            loop = asyncio.get_event_loop()
            
            # Пробуем войти с несколькими попытками и экспоненциальной задержкой
            for attempt in range(5):
                try:
                    logger.info(f"Attempting Garmin login for user {user_id}, attempt {attempt + 1}/5")
                    await loop.run_in_executor(None, garmin_client.login)
                    
                    logger.info(f"Successfully logged in user {user_id} on attempt {attempt + 1}")
                    
                    # Сохраняем сессию
                    self.active_sessions[user_id] = garmin_client
                    self.session_cache[user_id] = {
                        'username': tokens['username'],
                        'password': tokens['password'],
                        'garmin_user_id': tokens.get('garmin_user_id', ''),
                        'display_name': tokens.get('display_name', ''),
                        'created_at': datetime.now(),
                        'last_used': datetime.now(),
                        'restored_from_tokens': False
                    }
                    
                    # Сохраняем токены в файлы для будущего использования
                    token_save_success = token_manager.save_tokens(garmin_client)
                    if token_save_success:
                        logger.info(f"Successfully saved tokens to files after login for user {user_id}")
                    else:
                        logger.warning(f"Failed to save tokens to files after login for user {user_id}")
                    
                    return True
                    
                except Exception as e:
                    logger.warning(f"Garmin login attempt {attempt + 1} failed for user {user_id}: {str(e)}")
                    
                    if attempt == 4:  # Последняя попытка
                        logger.error(f"All Garmin login attempts failed for user {user_id}")
                        raise e
                    
                    # Экспоненциальная задержка: 2с, 4с, 8с, 16с
                    delay = min(2 ** attempt, 16)
                    logger.info(f"Waiting {delay}s before retry for user {user_id}")
                    await asyncio.sleep(delay)
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to restore Garmin session for user {user_id}: {str(e)}")
            return False
    
    async def _ensure_valid_session(self, user_id: int) -> Optional[Garmin]:
        """
        Убедиться что сессия пользователя активна и валидна
        Автоматически восстанавливает сессию если необходимо с улучшенной обработкой ошибок
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Optional[Garmin]: Валидный клиент Garmin или None
        """
        try:
            # Если сессии нет, пробуем восстановить
            if user_id not in self.active_sessions:
                logger.info(f"No active session for user {user_id}, attempting to restore")
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
                
                # Сессия недействительна, пробуем восстановить с несколькими попытками
                await self._cleanup_session(user_id)
                
                # Пробуем восстановить с несколькими попытками
                for attempt in range(3):
                    try:
                        logger.info(f"Attempting to restore Garmin session for user {user_id}, attempt {attempt + 1}")
                        restored = await self._restore_session(user_id)
                        
                        if restored:
                            logger.info(f"Successfully restored Garmin session for user {user_id} on attempt {attempt + 1}")
                            return self.active_sessions.get(user_id)
                        
                        # Если не удалось, ждем перед следующей попыткой
                        if attempt < 2:
                            delay = 2 ** attempt  # Экспоненциальная задержка
                            logger.info(f"Waiting {delay}s before next restore attempt for user {user_id}")
                            await asyncio.sleep(delay)
                            
                    except Exception as restore_error:
                        logger.error(f"Restore attempt {attempt + 1} failed for user {user_id}: {str(restore_error)}")
                        if attempt < 2:
                            delay = 2 ** attempt
                            await asyncio.sleep(delay)
                
                logger.error(f"Failed to restore Garmin session for user {user_id} after 3 attempts")
                return None
                
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
        """Получение токенов с основного бэкенда с улучшенной обработкой ошибок"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.backend_url}/garmin/get-tokens/{user_id}",
                    timeout=10.0
                )
            if response.status_code == 200:
                data = response.json()
                tokens = data.get('tokens')
                if tokens and tokens.get('username') and tokens.get('password'):
                    return tokens
                else:
                    logger.warning(f"Invalid tokens format for user {user_id}: missing username or password")
                    return None
            else:
                logger.warning(f"Backend returned status {response.status_code} for user {user_id}")
                return None
        except Exception as e:
            logger.error(f"Failed to get Garmin tokens from backend: {str(e)}")
            return None
    
    async def _send_activity_to_backend(self, user_id: int, activity: GarminActivity) -> bool:
        """Отправка активности на основной бэкенд"""
        try:
            # Конвертируем datetime в ISO строки для JSON сериализации
            activity_dict = activity.dict()
            if 'start_time' in activity_dict and activity_dict['start_time']:
                activity_dict['start_time'] = activity_dict['start_time'].isoformat()
            if 'end_time' in activity_dict and activity_dict['end_time']:
                activity_dict['end_time'] = activity_dict['end_time'].isoformat()
            
            activity_data = {
                "user_id": user_id,
                "activity": activity_dict
            }
            
            logger.info(f"Sending Garmin activity {activity.activity_id} to backend")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.backend_url}/garmin/activity",
                    json=activity_data,
                    timeout=30.0
                )
                
                logger.info(f"Backend response status: {response.status_code}")
                if response.status_code != 200:
                    logger.warning(f"Backend response body: {response.text}")
                else:
                    logger.info(f"Successfully synced Garmin activity {activity.activity_id}")
                
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send Garmin activity {activity.activity_id} to backend: {str(e)}")
            return False
    
    async def get_initial_activities(self, user_id: int, limit: int = 200) -> List[GarminActivity]:
        """
        Получить последние активности пользователя (для первоначальной синхронизации)
        
        Args:
            user_id: ID пользователя
            limit: Количество активностей для получения (по умолчанию 200)
            
        Returns:
            List[GarminActivity]: Список последних активностей
        """
        try:
            # Убедимся что сессия активна и валидна
            garmin_client = await self._ensure_valid_session(user_id)
            if not garmin_client:
                raise Exception("Нет активного подключения к Garmin")
            
            loop = asyncio.get_event_loop()
            
            # Получаем все активности без ограничения по дате
            activities_data = await loop.run_in_executor(None, garmin_client.get_activities)
            
            if not activities_data:
                return []
            
            # Сортируем по дате начала (новые первые) и ограничиваем количество
            activities_data.sort(key=lambda x: x.get('startTimeLocal', ''), reverse=True)
            limited_data = activities_data[:limit]
            
            # Конвертируем в нашу модель
            activities = []
            for activity in limited_data:
                garmin_activity = self._convert_to_garmin_activity(activity)
                if garmin_activity:
                    activities.append(garmin_activity)
            
            # Обновляем время последнего использования сессии
            if user_id in self.session_cache:
                self.session_cache[user_id]['last_used'] = datetime.now()
            
            return activities
            
        except Exception as e:
            logger.error(f"Error getting initial Garmin activities for user {user_id}: {str(e)}")
            raise Exception(f"Ошибка получения последних активностей: {str(e)}")
    
    async def download_fit_file(self, user_id: int, activity_id: str) -> Optional[str]:
        """
        Скачать .fit файл активности и вернуть путь к нему
        
        Args:
            user_id: ID пользователя
            activity_id: ID активности
            
        Returns:
            Optional[str]: Путь к .fit файлу или None в случае ошибки
        """
        try:
            # Убедимся что сессия активна и валидна
            garmin_client = await self._ensure_valid_session(user_id)
            if not garmin_client:
                raise Exception("Нет активного подключения к Garmin")
            
            loop = asyncio.get_event_loop()
            
            # Скачиваем zip архив
            logger.info(f"Downloading FIT file for activity {activity_id}")
            content = await loop.run_in_executor(
                None, 
                garmin_client.download_activity, 
                activity_id, 
                garmin_client.ActivityDownloadFormat.ORIGINAL
            )
            
            if not content:
                logger.error(f"No content received for activity {activity_id}")
                return None
            
            # Создаем временную директорию
            temp_dir = tempfile.mkdtemp(prefix=f"garmin_{user_id}_")
            zip_path = os.path.join(temp_dir, f"{activity_id}.zip")
            
            # Сохраняем zip файл
            with open(zip_path, 'wb') as f:
                f.write(content)
            
            # Распаковываем архив
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Ищем .fit файл
            for file in os.listdir(temp_dir):
                if file.endswith('.fit'):
                    fit_path = os.path.join(temp_dir, file)
                    logger.info(f"Successfully extracted FIT file: {fit_path}")
                    
                    # Отправляем FIT файл на бэкенд для обработки
                    await self._send_fit_file_to_backend(user_id, fit_path, activity_id)
                    
                    return fit_path
            
            # Если .fit файл не найден
            logger.error(f"No .fit file found in archive for activity {activity_id}")
            self._cleanup_temp_directory(temp_dir)
            return None
            
        except Exception as e:
            logger.error(f"Error downloading FIT file for activity {activity_id}: {str(e)}")
            return None
    
    def _cleanup_temp_directory(self, temp_dir: str):
        """Очистка временной директории"""
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp directory {temp_dir}: {str(e)}")
    
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
    
    async def get_token_info(self, user_id: int) -> Dict[str, Any]:
        """
        Получить информацию о токенах пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Dict[str, Any]: Информация о токенах
        """
        try:
            token_manager = TokenManager(user_id)
            token_info = token_manager.get_token_info()
            
            # Добавляем информацию о сессии
            if user_id in self.session_cache:
                session_info = self.session_cache[user_id]
                token_info.update({
                    'has_active_session': True,
                    'session_created_at': session_info.get('created_at'),
                    'session_last_used': session_info.get('last_used'),
                    'restored_from_tokens': session_info.get('restored_from_tokens', False)
                })
            else:
                token_info['has_active_session'] = False
                token_info['restored_from_tokens'] = False
            
            return token_info
            
        except Exception as e:
            logger.error(f"Failed to get token info for user {user_id}: {str(e)}")
            return {
                'user_id': user_id,
                'error': str(e),
                'tokens_valid': False,
                'has_active_session': False
            }

    async def _send_fit_file_to_backend(self, user_id: int, fit_path: str, activity_id: str):
        """
        Отправить FIT файл на бэкенд для обработки
        
        Args:
            user_id: ID пользователя
            fit_path: Путь к FIT файлу
            activity_id: ID активности
        """
        try:
            logger.info(f"Sending FIT file {fit_path} to backend for activity {activity_id}")
            
            # Читаем файл в память перед отправкой
            with open(fit_path, 'rb') as fit_file:
                file_content = fit_file.read()
            
            file_name = os.path.basename(fit_path)
            
            files = {
                'file': (file_name, file_content, 'application/octet-stream')
            }
            data = {
                'user_id': str(user_id),
                'source': 'garmin_fit_download',
                'garmin_activity_id': activity_id
            }
            
            # Пробуем отправить без авторизации (если эндпоинт позволяет)
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.backend_url}/activities/garmin-upload",
                    files=files,
                    data=data,
                    timeout=60.0
                )
                
                logger.info(f"Backend FIT upload response status: {response.status_code}")
                if response.status_code == 200:
                    logger.info(f"Successfully sent FIT file for activity {activity_id}")
                else:
                    logger.warning(f"Backend FIT upload response: {response.text}")
                    
                    # Если 401 (не авторизован), пробуем получить токены и повторить
                    if response.status_code == 401:
                        logger.info("Got 401, trying to get tokens and retry...")
                        tokens = await self._get_tokens_from_backend(user_id)
                        if tokens:
                            # Здесь нужно получить JWT токен пользователя, но у нас нет прямого доступа
                            # Пока просто логируем проблему
                            logger.warning("Cannot retry - need user JWT token for backend authentication")
                        
        except Exception as e:
            logger.error(f"Failed to send FIT file to backend for activity {activity_id}: {str(e)}")

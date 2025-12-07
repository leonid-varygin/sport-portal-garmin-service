import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from garminconnect import Garmin
from ..models import GarminAuthResponse
from ..config import settings

# Настройка логирования
logger = logging.getLogger(__name__)

class GarminAuthService:
    """
    Сервис аутентификации для работы с Garmin Connect API
    Управляет сессиями пользователей и процессом авторизации
    """
    
    def __init__(self):
        # Хранение активных сессий: {token: {'client': Garmin, 'created_at': datetime, 'username': str}}
        self._sessions: Dict[str, Dict[str, Any]] = {}
        # Время жизни сессии по умолчанию (24 часа)
        self._session_timeout = timedelta(hours=24)
        
    def _generate_token(self) -> str:
        """Генерирует уникальный токен сессии"""
        return str(uuid.uuid4())
    
    def _cleanup_expired_sessions(self):
        """Очищает устаревшие сессии"""
        current_time = datetime.now()
        expired_tokens = []
        
        for token, session_data in self._sessions.items():
            if current_time - session_data['created_at'] > self._session_timeout:
                expired_tokens.append(token)
        
        for token in expired_tokens:
            try:
                client = self._sessions[token]['client']
                # Пытаемся корректно выйти из Garmin
                asyncio.create_task(self._safe_logout(client))
                del self._sessions[token]
                logger.info(f"Cleaned up expired session for token: {token[:8]}...")
            except Exception as e:
                logger.error(f"Error cleaning up session {token[:8]}...: {e}")
                # Удаляем сессию даже если ошибка выхода
                if token in self._sessions:
                    del self._sessions[token]
    
    async def _safe_logout(self, client: Garmin):
        """Безопасный выход из Garmin с обработкой ошибок"""
        try:
            if hasattr(client, 'logout'):
                await client.logout()
        except Exception as e:
            logger.warning(f"Error during Garmin logout: {e}")
    
    async def authenticate(self, username: str, password: Optional[str] = None, oauth_code: Optional[str] = None) -> GarminAuthResponse:
        """
        Аутентификация пользователя в Garmin Connect
        
        Args:
            username: Имя пользователя Garmin
            password: Пароль (для password аутентификации)
            oauth_code: OAuth код (для OAuth аутентификации)
            
        Returns:
            GarminAuthResponse: Результат аутентификации
        """
        # Очищаем устаревшие сессии
        self._cleanup_expired_sessions()
        
        # Проверяем параметры
        if not password and not oauth_code:
            return GarminAuthResponse(
                success=False,
                error="Either password or oauth_code must be provided"
            )
        
        if not username:
            return GarminAuthResponse(
                success=False,
                error="Username is required"
            )
        
        # Создаем клиент Garmin
        client = Garmin()
        
        try:
            logger.info(f"Attempting authentication for user: {username}")
            
            # Аутентификация
            if password:
                # Password аутентификация
                login_success = await client.login(username, password)
            else:
                # OAuth аутентификация
                login_success = await client.login_with_oauth(oauth_code, username)
            
            if not login_success:
                return GarminAuthResponse(
                    success=False,
                    error="Authentication failed: Invalid credentials"
                )
            
            # Получаем информацию о пользователе
            try:
                user_profile = await client.get_user_profile()
                garmin_user_id = str(user_profile.get('userId', ''))
            except Exception as e:
                logger.warning(f"Failed to get user profile: {e}")
                garmin_user_id = ""
            
            # Генерируем токен сессии
            token = self._generate_token()
            
            # Сохраняем сессию
            self._sessions[token] = {
                'client': client,
                'created_at': datetime.now(),
                'username': username,
                'garmin_user_id': garmin_user_id
            }
            
            logger.info(f"Successfully authenticated user: {username}")
            
            # Возвращаем успешный результат
            return GarminAuthResponse(
                success=True,
                token=token,
                refresh_token=token,  # В нашей реализации используем тот же токен
                expires_at=datetime.now() + self._session_timeout,
                garmin_user_id=garmin_user_id
            )
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Authentication failed for user {username}: {error_message}")
            
            # Определяем тип ошибки для более точного сообщения
            if "invalid_credentials" in error_message.lower() or "authentication failed" in error_message.lower():
                error_msg = "Invalid username or password"
            elif "too many requests" in error_message.lower():
                error_msg = "Too many login attempts. Please try again later."
            elif "network" in error_message.lower() or "connection" in error_message.lower():
                error_msg = "Network error. Please check your connection and try again."
            elif "timeout" in error_message.lower():
                error_msg = "Request timeout. Garmin services may be unavailable."
            else:
                error_msg = f"Authentication error: {error_message}"
            
            return GarminAuthResponse(
                success=False,
                error=error_msg
            )
    
    def logout(self, token: str) -> bool:
        """
        Выход пользователя и удаление сессии
        
        Args:
            token: Токен сессии
            
        Returns:
            bool: Успешность операции
        """
        if token not in self._sessions:
            logger.warning(f"Attempted logout for non-existent token: {token[:8]}...")
            return False
        
        try:
            session_data = self._sessions[token]
            client = session_data['client']
            username = session_data['username']
            
            # Асинхронно выходим из Garmin
            asyncio.create_task(self._safe_logout(client))
            
            # Удаляем сессию
            del self._sessions[token]
            
            logger.info(f"Successfully logged out user: {username}")
            return True
            
        except Exception as e:
            logger.error(f"Error during logout for token {token[:8]}...: {e}")
            # Даже при ошибке удаляем сессию
            if token in self._sessions:
                del self._sessions[token]
            return False
    
    def get_client(self, token: str) -> Optional[Garmin]:
        """
        Получение клиента Garmin по токену с проверкой валидности
        
        Args:
            token: Токен сессии
            
        Returns:
            Optional[Garmin]: Клиент Garmin или None если токен невалиден
        """
        # Очищаем устаревшие сессии
        self._cleanup_expired_sessions()
        
        if token not in self._sessions:
            logger.warning(f"Client requested for non-existent token: {token[:8]}...")
            return None
        
        session_data = self._sessions[token]
        
        # Проверяем время жизни сессии
        if datetime.now() - session_data['created_at'] > self._session_timeout:
            logger.info(f"Session expired for token: {token[:8]}...")
            # Удаляем устаревшую сессию
            del self._sessions[token]
            return None
        
        return session_data['client']
    
    def verify_token(self, token: str) -> bool:
        """
        Проверка валидности токена
        
        Args:
            token: Токен сессии
            
        Returns:
            bool: True если токен валиден, иначе False
        """
        client = self.get_client(token)
        return client is not None
    
    def get_session_info(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Получение информации о сессии
        
        Args:
            token: Токен сессии
            
        Returns:
            Optional[Dict[str, Any]]: Информация о сессии или None
        """
        if token not in self._sessions:
            return None
        
        session_data = self._sessions[token]
        return {
            'username': session_data['username'],
            'created_at': session_data['created_at'],
            'garmin_user_id': session_data['garmin_user_id'],
            'expires_at': session_data['created_at'] + self._session_timeout
        }
    
    def refresh_session(self, token: str) -> bool:
        """
        Обновление времени жизни сессии
        
        Args:
            token: Токен сессии
            
        Returns:
            bool: Успешность операции
        """
        if token not in self._sessions:
            return False
        
        # Обновляем время создания сессии
        self._sessions[token]['created_at'] = datetime.now()
        logger.info(f"Session refreshed for token: {token[:8]}...")
        return True
    
    def get_active_sessions_count(self) -> int:
        """Получение количества активных сессий"""
        self._cleanup_expired_sessions()
        return len(self._sessions)
    
    def cleanup_all_sessions(self):
        """Очистка всех сессий (для administrative целей)"""
        logger.info("Cleaning up all sessions")
        
        for token in list(self._sessions.keys()):
            try:
                client = self._sessions[token]['client']
                asyncio.create_task(self._safe_logout(client))
            except Exception as e:
                logger.error(f"Error during session cleanup {token[:8]}...: {e}")
        
        self._sessions.clear()
        logger.info("All sessions cleaned up")

# Создаем глобальный экземпляр сервиса аутентификации
garmin_auth_service = GarminAuthService()

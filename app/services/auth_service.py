import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import garminconnect
from ..models.garmin_models import (
    GarminAuthRequest,
    GarminAuthResponse,
    GarminUserInfo,
    TokenValidationResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    LogoutResponse,
    AuthStatus
)

logger = logging.getLogger(__name__)


class AuthService:
    """Сервис авторизации Garmin с использованием библиотеки garminconnect"""
    
    def __init__(self):
        self.active_sessions: Dict[str, garminconnect.Garmin] = {}
        self.session_expiry: Dict[str, datetime] = {}
    
    async def authenticate(self, auth_request: GarminAuthRequest) -> GarminAuthResponse:
        """
        Аутентификация пользователя Garmin
        
        Args:
            auth_request: Данные для авторизации
            
        Returns:
            GarminAuthResponse: Результат авторизации
        """
        try:
            logger.info(f"Attempting authentication for user: {auth_request.username}")
            
            if not auth_request.password:
                return GarminAuthResponse(
                    success=False,
                    error="Password is required for authentication"
                )
            
            # Создаем клиент Garmin Connect
            client = garminconnect.Garmin(auth_request.username, auth_request.password)
            
            # Выполняем вход
            try:
                login_result = client.login()
                logger.info(f"Login successful for user: {auth_request.username}")
            except Exception as login_error:
                logger.error(f"Login failed for user {auth_request.username}: {str(login_error)}")
                return GarminAuthResponse(
                    success=False,
                    error=f"Authentication failed: {str(login_error)}"
                )
            
            # Получаем информацию о пользователе
            try:
                user_info = await self._get_user_info(client)
                garmin_user_id = user_info.get('displayName') or auth_request.username
            except Exception as info_error:
                logger.warning(f"Failed to get user info for {auth_request.username}: {str(info_error)}")
                garmin_user_id = auth_request.username
                user_info = None
            
            # Сохраняем сессию
            session_key = f"{auth_request.username}_{datetime.now().timestamp()}"
            self.active_sessions[session_key] = client
            
            # Устанавливаем время истечения сессии (обычно сессия Garmin действует ~1 час)
            expiry_time = datetime.now() + timedelta(hours=1)
            self.session_expiry[session_key] = expiry_time
            
            # Получаем токены из клиента (если доступны)
            token_data = self._extract_token_data(client)
            
            return GarminAuthResponse(
                success=True,
                token=token_data.get('token'),
                refresh_token=token_data.get('refresh_token'),
                expires_at=expiry_time,
                garmin_user_id=garmin_user_id
            )
            
        except Exception as e:
            logger.error(f"Authentication error for user {auth_request.username}: {str(e)}")
            return GarminAuthResponse(
                success=False,
                error=f"Authentication failed: {str(e)}"
            )
    
    async def validate_token(self, token: str) -> TokenValidationResponse:
        """
        Валидация токена
        
        Args:
            token: Токен для валидации
            
        Returns:
            TokenValidationResponse: Результат валидации
        """
        try:
            # Ищем сессию по токену
            session_key = self._find_session_by_token(token)
            
            if not session_key:
                return TokenValidationResponse(
                    valid=False,
                    status=AuthStatus.INVALID,
                    error="Token not found or invalid"
                )
            
            # Проверяем время истечения
            expiry_time = self.session_expiry.get(session_key)
            if expiry_time and datetime.now() >= expiry_time:
                # Удаляем истекшую сессию
                self._remove_session(session_key)
                return TokenValidationResponse(
                    valid=False,
                    status=AuthStatus.EXPIRED,
                    expires_at=expiry_time,
                    error="Token has expired"
                )
            
            # Проверяем активность сессии
            client = self.active_sessions.get(session_key)
            if not client:
                return TokenValidationResponse(
                    valid=False,
                    status=AuthStatus.INVALID,
                    error="Session not found"
                )
            
            # Получаем информацию о пользователе для проверки
            try:
                user_info = await self._get_user_info(client)
                return TokenValidationResponse(
                    valid=True,
                    status=AuthStatus.SUCCESS,
                    user_info=GarminUserInfo(**user_info) if user_info else None,
                    expires_at=expiry_time
                )
            except Exception as e:
                logger.warning(f"Failed to validate user session: {str(e)}")
                return TokenValidationResponse(
                    valid=False,
                    status=AuthStatus.ERROR,
                    error=f"Session validation failed: {str(e)}"
                )
                
        except Exception as e:
            logger.error(f"Token validation error: {str(e)}")
            return TokenValidationResponse(
                valid=False,
                status=AuthStatus.ERROR,
                error=f"Validation failed: {str(e)}"
            )
    
    async def refresh_token(self, refresh_request: RefreshTokenRequest) -> RefreshTokenResponse:
        """
        Обновление токена
        
        Args:
            refresh_request: Данные для обновления токена
            
        Returns:
            RefreshTokenResponse: Результат обновления токена
        """
        try:
            logger.info("Attempting to refresh token")
            
            # Ищем сессию по refresh_token
            session_key = self._find_session_by_refresh_token(refresh_request.refresh_token)
            
            if not session_key:
                return RefreshTokenResponse(
                    success=False,
                    error="Refresh token not found or invalid"
                )
            
            client = self.active_sessions.get(session_key)
            if not client:
                return RefreshTokenResponse(
                    success=False,
                    error="Session not found"
                )
            
            # Пытаемся обновить сессию
            try:
                # Garmin Connect обычно требует повторного входа для обновления
                # Но попробуем проверить текущий статус
                user_info = await self._get_user_info(client)
                
                # Обновляем время истечения
                new_expiry = datetime.now() + timedelta(hours=1)
                self.session_expiry[session_key] = new_expiry
                
                token_data = self._extract_token_data(client)
                
                return RefreshTokenResponse(
                    success=True,
                    token=token_data.get('token'),
                    refresh_token=token_data.get('refresh_token'),
                    expires_at=new_expiry
                )
                
            except Exception as refresh_error:
                logger.error(f"Token refresh failed: {str(refresh_error)}")
                # Удаляем нерабочую сессию
                self._remove_session(session_key)
                return RefreshTokenResponse(
                    success=False,
                    error=f"Token refresh failed: {str(refresh_error)}"
                )
                
        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}")
            return RefreshTokenResponse(
                success=False,
                error=f"Refresh failed: {str(e)}"
            )
    
    async def logout(self, token: str) -> LogoutResponse:
        """
        Выход из системы
        
        Args:
            token: Токен для выхода
            
        Returns:
            LogoutResponse: Результат выхода
        """
        try:
            session_key = self._find_session_by_token(token)
            
            if session_key:
                self._remove_session(session_key)
                return LogoutResponse(
                    success=True,
                    message="Successfully logged out"
                )
            else:
                return LogoutResponse(
                    success=False,
                    message="No active session found"
                )
                
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return LogoutResponse(
                success=False,
                message=f"Logout failed: {str(e)}"
            )
    
    def _extract_token_data(self, client: garminconnect.Garmin) -> Dict[str, str]:
        """Извлечение данных токена из клиента"""
        try:
            # Garmin Connect клиент хранит куки и сессионные данные
            # Возвращаем идентификатор сессии как токен
            return {
                'token': str(id(client)),
                'refresh_token': str(id(client)) + '_refresh'
            }
        except Exception:
            return {}
    
    def _find_session_by_token(self, token: str) -> Optional[str]:
        """Поиск сессии по токену"""
        for session_key, client in self.active_sessions.items():
            if str(id(client)) == token:
                return session_key
        return None
    
    def _find_session_by_refresh_token(self, refresh_token: str) -> Optional[str]:
        """Поиск сессии по refresh токену"""
        for session_key, client in self.active_sessions.items():
            if str(id(client)) + '_refresh' == refresh_token:
                return session_key
        return None
    
    def _remove_session(self, session_key: str) -> None:
        """Удаление сессии"""
        if session_key in self.active_sessions:
            del self.active_sessions[session_key]
        if session_key in self.session_expiry:
            del self.session_expiry[session_key]
    
    async def _get_user_info(self, client: garminconnect.Garmin) -> Optional[Dict[str, Any]]:
        """Получение информации о пользователе"""
        try:
            # Получаем профиль пользователя
            user_profile = client.get_user_profile()
            
            return {
                'displayName': user_profile.get('displayName'),
                'fullName': user_profile.get('fullName'),
                'userName': user_profile.get('userName'),
                'emailAddress': user_profile.get('emailAddress'),
                'age': user_profile.get('age'),
                'height': user_profile.get('height'),
                'weight': user_profile.get('weight'),
                'gender': user_profile.get('gender'),
                'timezone': user_profile.get('timeZone')
            }
        except Exception as e:
            logger.error(f"Failed to get user info: {str(e)}")
            return None
    
    def cleanup_expired_sessions(self) -> None:
        """Очистка истекших сессий"""
        current_time = datetime.now()
        expired_sessions = [
            session_key for session_key, expiry_time in self.session_expiry.items()
            if expiry_time and current_time >= expiry_time
        ]
        
        for session_key in expired_sessions:
            logger.info(f"Cleaning up expired session: {session_key}")
            self._remove_session(session_key)

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class AuthStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    EXPIRED = "expired"
    INVALID = "invalid"


class GarminAuthRequest(BaseModel):
    """Модель запроса авторизации Garmin"""
    username: str = Field(..., description="Имя пользователя Garmin")
    password: Optional[str] = Field(None, description="Пароль пользователя Garmin")
    oauth_code: Optional[str] = Field(None, description="OAuth код для авторизации")


class GarminAuthResponse(BaseModel):
    """Модель ответа авторизации Garmin"""
    success: bool = Field(..., description="Статус успешности авторизации")
    token: Optional[str] = Field(None, description="Токен доступа")
    refresh_token: Optional[str] = Field(None, description="Токен обновления")
    expires_at: Optional[datetime] = Field(None, description="Время истечения токена")
    garmin_user_id: Optional[str] = Field(None, description="ID пользователя Garmin")
    error: Optional[str] = Field(None, description="Сообщение об ошибке")


class GarminUserInfo(BaseModel):
    """Информация о пользователе Garmin"""
    displayName: Optional[str] = None
    fullName: Optional[str] = None
    userName: Optional[str] = None
    emailAddress: Optional[str] = None
    age: Optional[int] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    gender: Optional[str] = None
    timezone: Optional[str] = None


class TokenValidationResponse(BaseModel):
    """Ответ валидации токена"""
    valid: bool = Field(..., description="Валиден ли токен")
    status: AuthStatus = Field(..., description="Статус токена")
    user_info: Optional[GarminUserInfo] = Field(None, description="Информация о пользователе")
    expires_at: Optional[datetime] = Field(None, description="Время истечения токена")
    error: Optional[str] = Field(None, description="Сообщение об ошибке")


class RefreshTokenRequest(BaseModel):
    """Запрос на обновление токена"""
    refresh_token: str = Field(..., description="Refresh токен для обновления")


class RefreshTokenResponse(BaseModel):
    """Ответ на обновление токена"""
    success: bool = Field(..., description="Статус успешности обновления")
    token: Optional[str] = Field(None, description="Новый токен доступа")
    refresh_token: Optional[str] = Field(None, description="Новый токен обновления")
    expires_at: Optional[datetime] = Field(None, description="Новое время истечения токена")
    error: Optional[str] = Field(None, description="Сообщение об ошибке")


class LogoutResponse(BaseModel):
    """Ответ на logout"""
    success: bool = Field(..., description="Статус успешности выхода")
    message: str = Field(..., description="Сообщение")


class HealthCheckResponse(BaseModel):
    """Ответ health check"""
    status: str = Field(..., description="Статус сервиса")
    timestamp: datetime = Field(default_factory=datetime.now, description="Время проверки")
    version: Optional[str] = Field(None, description="Версия сервиса")

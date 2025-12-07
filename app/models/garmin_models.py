from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class GarminAuthStatus(str, Enum):
    """Статусы авторизации Garmin"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    EXPIRED = "expired"


class GarminAuthRequest(BaseModel):
    """Запрос на авторизацию в Garmin"""
    username: str = Field(..., description="Логин Garmin Connect")
    password: str = Field(..., description="Пароль Garmin Connect")
    user_id: int = Field(..., description="ID пользователя в системе")


class GarminAuthResponse(BaseModel):
    """Ответ авторизации Garmin"""
    success: bool
    status: GarminAuthStatus
    message: str
    garmin_user_id: Optional[str] = None
    display_name: Optional[str] = None


class GarminConnectionStatus(BaseModel):
    """Статус подключения Garmin"""
    connected: bool
    garmin_user_id: Optional[str] = None
    display_name: Optional[str] = None
    last_sync: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    message: Optional[str] = None


class GarminTokenInfo(BaseModel):
    """Информация о токенах Garmin"""
    token_type: str
    access_token: str
    refresh_token: str
    expires_at: datetime
    user_id: int
    garmin_user_id: str
    display_name: Optional[str] = None


class GarminActivity(BaseModel):
    """Модель активности Garmin"""
    activity_id: str
    activity_name: str
    activity_type: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[int] = None  # в секундах
    distance: Optional[float] = None  # в метрах
    average_hr: Optional[int] = None
    max_hr: Optional[int] = None
    calories: Optional[int] = None
    elevation_gain: Optional[float] = None
    avg_speed: Optional[float] = None
    max_speed: Optional[float] = None


class GarminSyncResult(BaseModel):
    """Результат синхронизации активностей"""
    success: bool
    synced: int = 0
    skipped: int = 0
    errors: List[str] = Field(default_factory=list)
    message: str


class GarminError(BaseModel):
    """Модель ошибки Garmin"""
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class GarminHeartRate(BaseModel):
    """Данные пульса"""
    timestamp: datetime
    heart_rate: int


class GarminSleepData(BaseModel):
    """Данные о сне"""
    sleep_date: datetime
    deep_sleep_seconds: int
    light_sleep_seconds: int
    rem_sleep_seconds: int
    awake_seconds: int
    total_sleep_seconds: int
    sleep_score: Optional[int] = None


class GarminStats(BaseModel):
    """Общая статистика Garmin"""
    total_activities: int
    total_distance: float
    total_duration: int
    last_activity_date: Optional[datetime] = None
    activities_this_month: int
    activities_this_year: int

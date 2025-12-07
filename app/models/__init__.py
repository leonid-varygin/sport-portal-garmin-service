"""
Модели данных для Garmin Auth Service
"""

from .garmin_models import (
    AuthStatus,
    GarminAuthRequest,
    GarminAuthResponse,
    GarminUserInfo,
    TokenValidationResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    LogoutResponse,
    HealthCheckResponse
)

__all__ = [
    "AuthStatus",
    "GarminAuthRequest",
    "GarminAuthResponse",
    "GarminUserInfo",
    "TokenValidationResponse",
    "RefreshTokenRequest",
    "RefreshTokenResponse",
    "LogoutResponse",
    "HealthCheckResponse"
]

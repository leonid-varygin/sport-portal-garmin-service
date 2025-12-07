from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from ..models import GarminAuthRequest, GarminAuthResponse
from ..services.garmin_service import garmin_service
from ..config import settings

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()

async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API key for internal communication"""
    if credentials.credentials != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials

@router.post("/login", response_model=GarminAuthResponse)
async def login(
    auth_request: GarminAuthRequest,
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Authenticate with Garmin Connect
    Supports both password and OAuth authentication
    """
    try:
        response = await garmin_service.authenticate(
            username=auth_request.username,
            password=auth_request.password,
            oauth_code=auth_request.oauth_code
        )
        
        if not response.success:
            raise HTTPException(status_code=401, detail=response.error)
            
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/logout")
async def logout(
    token: str,
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Logout and remove session
    """
    try:
        success = garmin_service.logout(token)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
            
        return {"message": "Logged out successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/verify")
async def verify_token(
    token: str,
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Verify if token is still valid
    """
    try:
        client = garmin_service.get_client(token)
        if not client:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
            
        return {"valid": True}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

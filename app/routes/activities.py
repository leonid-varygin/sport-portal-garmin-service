from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
from typing import Optional, List
from ..models import GarminActivity, GarminActivityDetails
from ..services.garmin_service import garmin_service
from ..config import settings

router = APIRouter(prefix="/activities", tags=["activities"])
security = HTTPBearer()

async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API key for internal communication"""
    if credentials.credentials != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials

@router.get("/", response_model=List[GarminActivity])
async def get_activities(
    token: str,
    start_date: Optional[datetime] = Query(None, description="Start date for activities"),
    end_date: Optional[datetime] = Query(None, description="End date for activities"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of activities to return"),
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Get activities from Garmin Connect
    """
    try:
        # Set default dates if not provided
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()
            
        activities = await garmin_service.get_activities(token, start_date, end_date, limit)
        return activities
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{activity_id}", response_model=GarminActivityDetails)
async def get_activity_details(
    activity_id: str,
    token: str,
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Get detailed activity information
    """
    try:
        activity_details = await garmin_service.get_activity_details(token, activity_id)
        return activity_details
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sync/recent")
async def sync_recent_activities(
    token: str,
    days: int = Query(7, ge=1, le=365, description="Number of days to sync"),
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Sync recent activities from the specified number of days
    """
    try:
        start_date = datetime.now() - timedelta(days=days)
        end_date = datetime.now()
        
        activities = await garmin_service.get_activities(token, start_date, end_date)
        
        return {
            "success": True,
            "synced_activities": len(activities),
            "period": {
                "start_date": start_date,
                "end_date": end_date
            },
            "activities": activities
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync/all")
async def sync_all_activities(
    token: str,
    start_date: Optional[datetime] = Query(None, description="Start date for sync"),
    end_date: Optional[datetime] = Query(None, description="End date for sync"),
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Sync all activities in the specified date range
    """
    try:
        # Set default dates if not provided (last 6 months)
        if not start_date:
            start_date = datetime.now() - timedelta(days=180)
        if not end_date:
            end_date = datetime.now()
            
        sync_response = await garmin_service.sync_user_data(token, start_date, end_date)
        return sync_response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

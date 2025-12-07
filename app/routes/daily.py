from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
from typing import Optional, List
from ..models import DailySteps, DailySummary
from ..services.garmin_service import garmin_service
from ..config import settings

router = APIRouter(prefix="/daily", tags=["daily data"])
security = HTTPBearer()

async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API key for internal communication"""
    if credentials.credentials != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials

@router.get("/steps/{date}", response_model=DailySteps)
async def get_daily_steps(
    date: datetime,
    token: str,
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Get daily steps data for specific date
    """
    try:
        steps_data = await garmin_service.get_daily_steps(token, date)
        return steps_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/summary/{date}", response_model=DailySummary)
async def get_daily_summary(
    date: datetime,
    token: str,
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Get comprehensive daily summary including sleep, stress, etc.
    """
    try:
        summary_data = await garmin_service.get_daily_summary(token, date)
        return summary_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/steps/range")
async def get_steps_range(
    token: str,
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Get daily steps data for a date range
    """
    try:
        # Set default dates if not provided (last 30 days)
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()
            
        steps_data = []
        current_date = start_date
        
        while current_date <= end_date:
            try:
                daily_steps = await garmin_service.get_daily_steps(token, current_date)
                steps_data.append(daily_steps)
            except Exception as e:
                # Continue with next date if one fails
                pass
            
            current_date += timedelta(days=1)
        
        return {
            "success": True,
            "period": {
                "start_date": start_date,
                "end_date": end_date
            },
            "total_days": len(steps_data),
            "data": steps_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/summary/range")
async def get_summary_range(
    token: str,
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Get daily summary data for a date range
    """
    try:
        # Set default dates if not provided (last 7 days for comprehensive data)
        if not start_date:
            start_date = datetime.now() - timedelta(days=7)
        if not end_date:
            end_date = datetime.now()
            
        summary_data = []
        current_date = start_date
        
        while current_date <= end_date:
            try:
                daily_summary = await garmin_service.get_daily_summary(token, current_date)
                summary_data.append(daily_summary)
            except Exception as e:
                # Continue with next date if one fails
                pass
            
            current_date += timedelta(days=1)
        
        return {
            "success": True,
            "period": {
                "start_date": start_date,
                "end_date": end_date
            },
            "total_days": len(summary_data),
            "data": summary_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/today")
async def get_today_data(
    token: str,
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Get today's comprehensive data
    """
    try:
        today = datetime.now()
        
        # Get both steps and summary
        steps_data = await garmin_service.get_daily_steps(token, today)
        summary_data = await garmin_service.get_daily_summary(token, today)
        
        return {
            "date": today,
            "steps": steps_data,
            "summary": summary_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync")
async def sync_daily_data(
    token: str,
    start_date: Optional[datetime] = Query(None, description="Start date for sync"),
    end_date: Optional[datetime] = Query(None, description="End date for sync"),
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Sync daily data for the specified date range
    """
    try:
        # Set default dates if not provided (last 30 days)
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()
            
        sync_response = await garmin_service.sync_user_data(token, start_date, end_date)
        return sync_response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

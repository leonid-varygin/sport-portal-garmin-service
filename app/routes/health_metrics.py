from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
from typing import Optional, List
from ..models import HealthMetrics, AdvancedHealthMetrics, DailyMetrics, HealthMetricsSyncResponse
from ..services.garmin_service import garmin_service
from ..config import settings

router = APIRouter(prefix="/health-metrics", tags=["health metrics"])
security = HTTPBearer()

async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API key for internal communication"""
    if credentials.credentials != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials

@router.get("/basic/{date}", response_model=HealthMetrics)
async def get_health_metrics(
    date: datetime,
    token: str = Query(..., description="Garmin token"),
    user_id: str = Query(..., description="User ID"),
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Get basic health metrics for specific date
    """
    try:
        health_metrics = await garmin_service.get_health_metrics(token, date, user_id)
        return health_metrics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/advanced/{date}", response_model=AdvancedHealthMetrics)
async def get_advanced_health_metrics(
    date: datetime,
    token: str = Query(..., description="Garmin token"),
    user_id: str = Query(..., description="User ID"),
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Get advanced health metrics for specific date
    """
    try:
        advanced_metrics = await garmin_service.get_advanced_health_metrics(token, date, user_id)
        return advanced_metrics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/complete/{date}", response_model=DailyMetrics)
async def get_daily_metrics(
    date: datetime,
    token: str = Query(..., description="Garmin token"),
    user_id: str = Query(..., description="User ID"),
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Get complete daily metrics including both basic and advanced health metrics
    """
    try:
        daily_metrics = await garmin_service.get_daily_metrics(token, date, user_id)
        return daily_metrics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/basic/range")
async def get_health_metrics_range(
    token: str = Query(..., description="Garmin token"),
    user_id: str = Query(..., description="User ID"),
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Get basic health metrics for a date range
    """
    try:
        # Set default dates if not provided (last 7 days for health metrics)
        if not start_date:
            start_date = datetime.now() - timedelta(days=7)
        if not end_date:
            end_date = datetime.now()
            
        health_metrics_data = []
        current_date = start_date
        
        while current_date <= end_date:
            try:
                daily_health_metrics = await garmin_service.get_health_metrics(token, current_date, user_id)
                health_metrics_data.append(daily_health_metrics)
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
            "total_days": len(health_metrics_data),
            "data": health_metrics_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/advanced/range")
async def get_advanced_health_metrics_range(
    token: str = Query(..., description="Garmin token"),
    user_id: str = Query(..., description="User ID"),
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Get advanced health metrics for a date range
    """
    try:
        # Set default dates if not provided (last 7 days for health metrics)
        if not start_date:
            start_date = datetime.now() - timedelta(days=7)
        if not end_date:
            end_date = datetime.now()
            
        advanced_metrics_data = []
        current_date = start_date
        
        while current_date <= end_date:
            try:
                daily_advanced_metrics = await garmin_service.get_advanced_health_metrics(token, current_date, user_id)
                advanced_metrics_data.append(daily_advanced_metrics)
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
            "total_days": len(advanced_metrics_data),
            "data": advanced_metrics_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/complete/range")
async def get_daily_metrics_range(
    token: str = Query(..., description="Garmin token"),
    user_id: str = Query(..., description="User ID"),
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Get complete daily metrics for a date range
    """
    try:
        # Set default dates if not provided (last 7 days for health metrics)
        if not start_date:
            start_date = datetime.now() - timedelta(days=7)
        if not end_date:
            end_date = datetime.now()
            
        daily_metrics_data = []
        current_date = start_date
        
        while current_date <= end_date:
            try:
                daily_metrics = await garmin_service.get_daily_metrics(token, current_date, user_id)
                daily_metrics_data.append(daily_metrics)
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
            "total_days": len(daily_metrics_data),
            "data": daily_metrics_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/today")
async def get_today_health_metrics(
    token: str = Query(..., description="Garmin token"),
    user_id: str = Query(..., description="User ID"),
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Get today's complete health metrics
    """
    try:
        today = datetime.now()
        daily_metrics = await garmin_service.get_daily_metrics(token, today, user_id)
        return daily_metrics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync", response_model=HealthMetricsSyncResponse)
async def sync_health_metrics(
    token: str = Query(..., description="Garmin token"),
    user_id: str = Query(..., description="User ID"),
    start_date: Optional[datetime] = Query(None, description="Start date for sync"),
    end_date: Optional[datetime] = Query(None, description="End date for sync"),
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Sync health metrics for specified date range
    """
    try:
        sync_response = await garmin_service.sync_health_metrics(
            token, start_date, end_date, user_id
        )
        return sync_response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync/morning")
async def sync_morning_health_metrics(
    token: str = Query(..., description="Garmin token"),
    user_id: str = Query(..., description="User ID"),
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Sync morning health metrics (typically called in the morning)
    Gets data from yesterday and today
    """
    try:
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        
        # Sync yesterday's data (to get complete sleep data)
        yesterday_response = await garmin_service.sync_health_metrics(
            token, yesterday, yesterday, user_id
        )
        
        # Sync today's morning data
        today_response = await garmin_service.sync_health_metrics(
            token, today, today, user_id
        )
        
        # Combine responses
        combined_response = HealthMetricsSyncResponse(
            success=yesterday_response.success and today_response.success,
            synced_days=yesterday_response.synced_days + today_response.synced_days,
            errors=yesterday_response.errors + today_response.errors,
            last_sync_time=datetime.now(),
            metrics_type="morning"
        )
        
        return combined_response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync/evening")
async def sync_evening_health_metrics(
    token: str = Query(..., description="Garmin token"),
    user_id: str = Query(..., description="User ID"),
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Sync evening health metrics (typically called in the evening)
    Gets today's complete data
    """
    try:
        today = datetime.now()
        
        # Sync today's complete data
        sync_response = await garmin_service.sync_health_metrics(
            token, today, today, user_id
        )
        
        # Update response type
        sync_response.metrics_type = "evening"
        
        return sync_response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/summary/{date}")
async def get_health_metrics_summary(
    date: datetime,
    token: str = Query(..., description="Garmin token"),
    user_id: str = Query(..., description="User ID"),
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Get a summary of health metrics for a specific date
    Returns key health indicators in a simplified format
    """
    try:
        daily_metrics = await garmin_service.get_daily_metrics(token, date, user_id)
        
        # Extract key metrics for summary
        health_data = daily_metrics.healthMetrics
        
        summary = {
            "date": date,
            "userId": user_id,
            "keyMetrics": {
                "restingHeartRate": health_data.restingHeartRate,
                "avgHeartRate": health_data.avgHeartRate,
                "sleepScore": None,  # Extract from sleep data if available
                "stressLevel": None,  # Extract from stress data if available
                "bodyBattery": None,  # Extract from body battery data if available
                "spo2": health_data.spo2,
                "weight": health_data.weight,
                "vo2Max": health_data.vo2Max,
                "trainingReadiness": None  # Extract from training readiness if available
            },
            "hasAdvancedData": daily_metrics.advancedMetrics is not None,
            "syncedAt": daily_metrics.syncedAt
        }
        
        # Extract additional details from nested data if available
        if health_data.sleep and isinstance(health_data.sleep, dict):
            summary["keyMetrics"]["sleepScore"] = health_data.sleep.get("sleepScore")
        
        if health_data.stress and isinstance(health_data.stress, dict):
            summary["keyMetrics"]["stressLevel"] = health_data.stress.get("avgStressLevel")
        
        if health_data.bodyBattery and isinstance(health_data.bodyBattery, dict):
            summary["keyMetrics"]["bodyBattery"] = health_data.bodyBattery.get("bodyBattery")
        
        if health_data.trainingReadiness and isinstance(health_data.trainingReadiness, dict):
            summary["keyMetrics"]["trainingReadiness"] = health_data.trainingReadiness.get("score")
        
        return summary
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_health_metrics_status(
    token: str = Query(..., description="Garmin token"),
    user_id: str = Query(..., description="User ID"),
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Get the status of health metrics availability
    Checks which metrics are available for recent dates
    """
    try:
        today = datetime.now()
        status_data = {}
        
        # Check last 7 days
        for days_ago in range(7):
            check_date = today - timedelta(days=days_ago)
            date_str = check_date.strftime('%Y-%m-%d')
            
            try:
                daily_metrics = await garmin_service.get_daily_metrics(token, check_date, user_id)
                
                # Check which data types are available
                health_data = daily_metrics.healthMetrics
                
                status_data[date_str] = {
                    "hasData": True,
                    "hasHeartRate": health_data.restingHeartRate is not None,
                    "hasHRV": health_data.hrv is not None,
                    "hasSleep": health_data.sleep is not None,
                    "hasStress": health_data.stress is not None,
                    "hasBodyBattery": health_data.bodyBattery is not None,
                    "hasSpO2": health_data.spo2 is not None,
                    "hasWeight": health_data.weight is not None,
                    "hasVO2Max": health_data.vo2Max is not None,
                    "hasAdvancedData": daily_metrics.advancedMetrics is not None,
                    "lastSync": daily_metrics.syncedAt
                }
                
            except Exception:
                status_data[date_str] = {
                    "hasData": False,
                    "error": "No data available"
                }
        
        return {
            "userId": user_id,
            "checkedDates": list(status_data.keys()),
            "status": status_data,
            "checkedAt": datetime.now()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

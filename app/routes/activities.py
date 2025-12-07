from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from ..models import GarminActivity, GarminActivityDetails, SyncResponse, FitFileInfo, FitFilesResponse
from ..services import garmin_service, garmin_auth_service
from ..config import settings

router = APIRouter(prefix="/activities", tags=["activities"])
security = HTTPBearer()

async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API key for internal communication"""
    if credentials.credentials != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials

async def get_garmin_client(token: str = Query(..., description="Garmin authentication token")):
    """Get authenticated Garmin client"""
    client = garmin_auth_service.get_client(token)
    if not client:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return client

@router.get("/", response_model=List[GarminActivity])
async def get_activities(
    token: str,
    start_date: Optional[datetime] = Query(None, description="Start date for activities"),
    end_date: Optional[datetime] = Query(None, description="End date for activities"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of activities to return"),
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Get activities from Garmin Connect using download_activities method
    """
    try:
        # Set default dates if not provided
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()
        
        # Get authenticated client
        client = garmin_auth_service.get_client(token)
        if not client:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
            
        activities = await garmin_service.get_activities(client, start_date, end_date, limit)
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
        # Get authenticated client
        client = garmin_auth_service.get_client(token)
        if not client:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
            
        activity_details = await garmin_service.get_activity_details(client, activity_id)
        return activity_details
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download/fit")
async def download_fit_files(
    token: str,
    start_date: Optional[datetime] = Query(None, description="Start date for FIT files download"),
    end_date: Optional[datetime] = Query(None, description="End date for FIT files download"),
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Download FIT files for activities in date range using download_activities method
    """
    try:
        # Set default dates if not provided
        if not start_date:
            start_date = datetime.now() - timedelta(days=7)  # Last week by default
        if not end_date:
            end_date = datetime.now()
        
        # Get authenticated client
        client = garmin_auth_service.get_client(token)
        if not client:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        # Download FIT files using the download_activities method
        fit_files = await garmin_service.download_fit_files(client, start_date, end_date)
        
        return {
            "success": True,
            "downloaded_files": len(fit_files),
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "files": fit_files
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{activity_id}/fit")
async def download_single_fit_file(
    activity_id: str,
    token: str,
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Download FIT file for a specific activity
    """
    try:
        # Get authenticated client
        client = garmin_auth_service.get_client(token)
        if not client:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        # Download FIT file for specific activity
        fit_data = await client.download_activity_fit(activity_id)
        
        if not fit_data:
            raise HTTPException(status_code=404, detail="FIT file not found for this activity")
        
        # Return the FIT file as binary data
        return Response(
            content=fit_data,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename=activity_{activity_id}.fit"
            }
        )
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="FIT file not found for this activity")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sync/recent")
async def sync_recent_activities(
    token: str,
    days: int = Query(7, ge=1, le=365, description="Number of days to sync"),
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Sync recent activities from the specified number of days using download_activities
    """
    try:
        start_date = datetime.now() - timedelta(days=days)
        end_date = datetime.now()
        
        # Get authenticated client
        client = garmin_auth_service.get_client(token)
        if not client:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        # Get activities using download_activities method
        activities = await garmin_service.get_activities(client, start_date, end_date)
        
        return {
            "success": True,
            "synced_activities": len(activities),
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
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
    Sync all activities and FIT files in the specified date range using download_activities
    """
    try:
        # Set default dates if not provided (last 6 months)
        if not start_date:
            start_date = datetime.now() - timedelta(days=180)
        if not end_date:
            end_date = datetime.now()
        
        # Get authenticated client
        client = garmin_auth_service.get_client(token)
        if not client:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
            
        sync_response = await garmin_service.sync_user_data(client, start_date, end_date)
        return sync_response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download/fit/batch")
async def download_fit_files_batch(
    token: str,
    start_date: Optional[datetime] = Query(None, description="Start date for batch download"),
    end_date: Optional[datetime] = Query(None, description="End date for batch download"),
    _: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Download multiple FIT files in a single request using download_activities method
    This endpoint specifically uses the download_activities method as requested
    """
    try:
        # Set default dates if not provided
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()
        
        # Get authenticated client
        client = garmin_auth_service.get_client(token)
        if not client:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        # Use download_activities method to get activities first
        activities_data = await client.download_activities(
            startdate=start_date.isoformat(),
            enddate=end_date.isoformat()
        )
        
        downloaded_files = []
        errors = []
        
        # Download FIT files for each activity
        for activity in activities_data:
            try:
                activity_id = activity.get('activityId')
                activity_name = activity.get('activityName', f'Activity_{activity_id}')
                
                # Download FIT file
                fit_data = await client.download_activity_fit(activity_id)
                
                if fit_data:
                    file_info = {
                        'activity_id': str(activity_id),
                        'activity_name': activity_name,
                        'start_time': activity.get('startTimeLocal'),
                        'activity_type': activity.get('activityType', {}).get('typeKey', ''),
                        'fit_data': fit_data,
                        'file_size': len(fit_data) if isinstance(fit_data, bytes) else 0,
                        'downloaded_at': datetime.now().isoformat()
                    }
                    downloaded_files.append(file_info)
                else:
                    errors.append(f"No FIT data available for activity {activity_id}")
                    
            except Exception as e:
                activity_id = activity.get('activityId', 'unknown')
                errors.append(f"Error downloading FIT file for activity {activity_id}: {str(e)}")
                continue
        
        return {
            "success": True,
            "total_activities": len(activities_data),
            "downloaded_files": len(downloaded_files),
            "errors_count": len(errors),
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "files": downloaded_files,
            "errors": errors
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

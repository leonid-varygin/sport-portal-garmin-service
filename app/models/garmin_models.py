from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class GarminAuthRequest(BaseModel):
    username: str
    password: Optional[str] = None
    oauth_code: Optional[str] = None

class GarminAuthResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    garmin_user_id: Optional[str] = None
    error: Optional[str] = None

class GarminActivity(BaseModel):
    activityId: str
    activityName: str
    activityType: str
    startTimeLocal: datetime
    startTimeGMT: datetime
    duration: Optional[float] = None
    distance: Optional[float] = None
    averageSpeed: Optional[float] = None
    maxSpeed: Optional[float] = None
    averageHR: Optional[int] = None
    maxHR: Optional[int] = None
    averagePower: Optional[float] = None
    maxPower: Optional[float] = None
    calories: Optional[int] = None
    elevationGain: Optional[float] = None
    elevationLoss: Optional[float] = None
    avgCadence: Optional[float] = None
    maxCadence: Optional[float] = None
    trainingEffect: Optional[Dict[str, Any]] = None
    activityTypeKey: Optional[str] = None
    sportTypeKey: Optional[str] = None

class GarminActivityDetails(BaseModel):
    activityId: str
    activityName: str
    description: Optional[str] = None
    activityType: Dict[str, Any]
    startTimeLocal: datetime
    startTimeGMT: datetime
    duration: float
    distance: float
    averageSpeed: float
    maxSpeed: float
    averageHR: Optional[int] = None
    maxHR: Optional[int] = None
    averagePower: Optional[float] = None
    maxPower: Optional[float] = None
    calories: int
    elevationGain: Optional[float] = None
    elevationLoss: Optional[float] = None
    avgCadence: Optional[float] = None
    maxCadence: Optional[float] = None
    steps: Optional[int] = None
    avgVerticalOscillation: Optional[float] = None
    avgGroundContactTime: Optional[float] = None
    avgStrideLength: Optional[float] = None
    vo2Max: Optional[float] = None
    trainingEffect: Optional[Dict[str, Any]] = None
    maxVerticalSpeed: Optional[float] = None
    sampleType: Optional[str] = None

class DailySteps(BaseModel):
    date: datetime
    steps: int
    distance: Optional[float] = None
    calories: Optional[int] = None
    floorsClimbed: Optional[int] = None
    minutesModerateIntensity: Optional[int] = None
    minutesVigorousIntensity: Optional[int] = None
    avgStressLevel: Optional[float] = None
    restingHeartRate: Optional[int] = None

class DailySummary(BaseModel):
    date: datetime
    steps: DailySteps
    restingHeartRate: Optional[int] = None
    sleep: Optional[Dict[str, Any]] = None
    stress: Optional[Dict[str, Any]] = None
    bodyBattery: Optional[Dict[str, Any]] = None
    hydration: Optional[float] = None
    weight: Optional[float] = None

class GarminUserStats(BaseModel):
    userDailyGoals: Dict[str, Any]
    totalSteps: int
    totalDistance: float
    totalCalories: int
    totalFloorsClimbed: int
    totalActivities: int
    totalDuration: float

class SyncRequest(BaseModel):
    user_id: int
    garmin_token: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class SyncResponse(BaseModel):
    success: bool
    synced_activities: int
    synced_days: int
    errors: List[str] = []
    last_sync_time: Optional[datetime] = None

# Health Metrics Models
class HealthMetrics(BaseModel):
    date: datetime
    restingHeartRate: Optional[int] = None
    maxHeartRate: Optional[int] = None
    avgHeartRate: Optional[float] = None
    hrv: Optional[Dict[str, Any]] = None
    stress: Optional[Dict[str, Any]] = None
    sleep: Optional[Dict[str, Any]] = None
    bodyBattery: Optional[Dict[str, Any]] = None
    spo2: Optional[float] = None
    weight: Optional[float] = None
    bodyFat: Optional[float] = None
    bodyMassIndex: Optional[float] = None
    muscleMass: Optional[float] = None
    boneMass: Optional[float] = None
    bodyWater: Optional[float] = None
    visceralFat: Optional[float] = None
    hydration: Optional[float] = None
    vo2Max: Optional[float] = None
    trainingReadiness: Optional[Dict[str, Any]] = None
    respiration: Optional[Dict[str, Any]] = None
    pulseOx: Optional[Dict[str, Any]] = None
    # Activity Metrics
    steps: Optional[int] = None
    calories: Optional[int] = None

class AdvancedHealthMetrics(BaseModel):
    date: datetime
    sleepDetails: Optional[Dict[str, Any]] = None
    stressDetails: Optional[Dict[str, Any]] = None
    hrvDetails: Optional[Dict[str, Any]] = None
    bodyBatteryDetails: Optional[Dict[str, Any]] = None
    trainingReadinessDetails: Optional[Dict[str, Any]] = None
    wellnessData: Optional[Dict[str, Any]] = None
    healthSnapshot: Optional[Dict[str, Any]] = None

class DailyMetrics(BaseModel):
    date: datetime
    userId: str
    healthMetrics: HealthMetrics
    advancedMetrics: Optional[AdvancedHealthMetrics] = None
    syncedAt: datetime
    
class HealthMetricsSyncResponse(BaseModel):
    success: bool
    synced_days: int
    errors: List[str] = []
    last_sync_time: Optional[datetime] = None
    metrics_type: str  # 'basic' or 'advanced'

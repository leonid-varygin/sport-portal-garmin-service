import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from garminconnect import Garmin
from ..models import (
    GarminAuthResponse, 
    GarminActivity, 
    GarminActivityDetails, 
    DailySteps, 
    DailySummary,
    SyncResponse,
    HealthMetrics,
    AdvancedHealthMetrics,
    DailyMetrics,
    HealthMetricsSyncResponse
)

logger = logging.getLogger(__name__)

class GarminService:
    def __init__(self):
        self.active_sessions: Dict[str, Garmin] = {}
        
    async def authenticate(self, username: str, password: Optional[str] = None, oauth_code: Optional[str] = None) -> GarminAuthResponse:
        """
        Authenticate with Garmin Connect
        Supports both password and OAuth authentication
        """
        try:
            garmin_client = Garmin(username, password)
            
            if password:
                # Password authentication - login() is synchronous, returns tuple
                login_result = garmin_client.login()
                if login_result[0]:  # Success
                    logger.info(f"Successfully authenticated user {username} with password")
                else:
                    logger.error(f"Login failed for user {username}")
                    return GarminAuthResponse(
                        success=False,
                        error="Login failed - invalid credentials"
                    )
            elif oauth_code:
                # OAuth authentication - check if method exists and is async
                if hasattr(garmin_client, 'login_with_oauth'):
                    try:
                        await garmin_client.login_with_oauth(oauth_code)
                        logger.info(f"Successfully authenticated user {username} with OAuth")
                    except TypeError:
                        # If not async, try sync
                        garmin_client.login_with_oauth(oauth_code)
                        logger.info(f"Successfully authenticated user {username} with OAuth (sync)")
                else:
                    return GarminAuthResponse(
                        success=False,
                        error="OAuth authentication not supported"
                    )
            else:
                return GarminAuthResponse(
                    success=False,
                    error="Either password or oauth_code must be provided"
                )
            
            # Get user profile - check if async
            try:
                profile = await garmin_client.get_user_profile()
            except TypeError:
                # If not async, try sync
                profile = garmin_client.get_user_profile()
            
            garmin_user_id = profile.get('displayName', username)
            
            # Store session
            session_token = f"{username}_{datetime.now().timestamp()}"
            self.active_sessions[session_token] = garmin_client
            
            return GarminAuthResponse(
                success=True,
                token=session_token,
                refresh_token=session_token,  # Using same token for simplicity
                expires_at=datetime.now() + timedelta(hours=24),
                garmin_user_id=garmin_user_id
            )
            
        except Exception as e:
            logger.error(f"Authentication failed for user {username}: {str(e)}")
            return GarminAuthResponse(
                success=False,
                error=str(e)
            )
    
    def get_client(self, token: str) -> Optional[Garmin]:
        """Get Garmin client from active sessions"""
        return self.active_sessions.get(token)
    
    async def get_activities(self, token: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, limit: int = 100) -> List[GarminActivity]:
        """
        Get activities from Garmin Connect
        """
        garmin_client = self.get_client(token)
        if not garmin_client:
            raise Exception("Invalid or expired token")
        
        try:
            # Convert datetime objects to strings as expected by garminconnect
            start_date_str = (start_date or (datetime.now() - timedelta(days=30))).strftime('%Y-%m-%d')
            end_date_str = (end_date or datetime.now()).strftime('%Y-%m-%d')
            
            # Use the correct method with proper parameter names
            activities_data = []
            
            try:
                # Try async first
                activities_data = await garmin_client.get_activities_by_date(
                    startdate=start_date_str,
                    enddate=end_date_str
                )
            except TypeError:
                # If not async, try sync
                activities_data = garmin_client.get_activities_by_date(
                    startdate=start_date_str,
                    enddate=end_date_str
                )
            
            activities = []
            for activity_data in activities_data[:limit]:
                activity = GarminActivity(
                    activityId=str(activity_data.get('activityId', '')),
                    activityName=activity_data.get('activityName', ''),
                    activityType=activity_data.get('activityType', {}).get('typeKey', ''),
                    startTimeLocal=datetime.fromisoformat(activity_data.get('startTimeLocal', '')),
                    startTimeGMT=datetime.fromisoformat(activity_data.get('startTimeGMT', '')),
                    duration=activity_data.get('duration'),
                    distance=activity_data.get('distance'),
                    averageSpeed=activity_data.get('averageSpeed'),
                    maxSpeed=activity_data.get('maxSpeed'),
                    averageHR=activity_data.get('averageHR'),
                    maxHR=activity_data.get('maxHR'),
                    averagePower=activity_data.get('averagePower'),
                    maxPower=activity_data.get('maxPower'),
                    calories=activity_data.get('calories'),
                    elevationGain=activity_data.get('elevationGain'),
                    elevationLoss=activity_data.get('elevationLoss'),
                    avgCadence=activity_data.get('avgCadence'),
                    maxCadence=activity_data.get('maxCadence'),
                    trainingEffect=activity_data.get('trainingEffect'),
                    activityTypeKey=activity_data.get('activityType', {}).get('typeKey'),
                    sportTypeKey=activity_data.get('sportType', {}).get('typeKey')
                )
                activities.append(activity)
            
            logger.info(f"Retrieved {len(activities)} activities")
            return activities
            
        except Exception as e:
            logger.error(f"Failed to get activities: {str(e)}")
            raise Exception(f"Failed to get activities: {str(e)}")
    
    async def get_activity_details(self, token: str, activity_id: str) -> GarminActivityDetails:
        """
        Get detailed activity information
        """
        garmin_client = self.get_client(token)
        if not garmin_client:
            raise Exception("Invalid or expired token")
        
        try:
            # Check if get_activity_details is async
            try:
                activity_data = await garmin_client.get_activity_details(activity_id)
            except TypeError:
                # If not async, try sync
                activity_data = garmin_client.get_activity_details(activity_id)
            
            activity_details = GarminActivityDetails(
                activityId=str(activity_data.get('activityId', '')),
                activityName=activity_data.get('activityName', ''),
                description=activity_data.get('description'),
                activityType=activity_data.get('activityType', {}),
                startTimeLocal=datetime.fromisoformat(activity_data.get('startTimeLocal', '')),
                startTimeGMT=datetime.fromisoformat(activity_data.get('startTimeGMT', '')),
                duration=activity_data.get('duration', 0),
                distance=activity_data.get('distance', 0),
                averageSpeed=activity_data.get('averageSpeed', 0),
                maxSpeed=activity_data.get('maxSpeed', 0),
                averageHR=activity_data.get('averageHR'),
                maxHR=activity_data.get('maxHR'),
                averagePower=activity_data.get('averagePower'),
                maxPower=activity_data.get('maxPower'),
                calories=activity_data.get('calories', 0),
                elevationGain=activity_data.get('elevationGain'),
                elevationLoss=activity_data.get('elevationLoss'),
                avgCadence=activity_data.get('avgCadence'),
                maxCadence=activity_data.get('maxCadence'),
                steps=activity_data.get('steps'),
                avgVerticalOscillation=activity_data.get('avgVerticalOscillation'),
                avgGroundContactTime=activity_data.get('avgGroundContactTime'),
                avgStrideLength=activity_data.get('avgStrideLength'),
                vo2Max=activity_data.get('vo2Max'),
                trainingEffect=activity_data.get('trainingEffect'),
                maxVerticalSpeed=activity_data.get('maxVerticalSpeed'),
                sampleType=activity_data.get('sampleType')
            )
            
            logger.info(f"Retrieved details for activity {activity_id}")
            return activity_details
            
        except Exception as e:
            logger.error(f"Failed to get activity details for {activity_id}: {str(e)}")
            raise Exception(f"Failed to get activity details: {str(e)}")
    
    async def get_daily_steps(self, token: str, date: datetime) -> DailySteps:
        """
        Get daily steps data
        """
        garmin_client = self.get_client(token)
        if not garmin_client:
            raise Exception("Invalid or expired token")
        
        try:
            date_str = date.strftime('%Y-%m-%d')
            
            # Check if get_steps_data is async
            try:
                steps_data = await garmin_client.get_steps_data(date_str)
            except TypeError:
                # If not async, try sync
                steps_data = garmin_client.get_steps_data(date_str)
            
            daily_steps = DailySteps(
                date=date,
                steps=steps_data.get('totalSteps', 0),
                distance=steps_data.get('totalDistance'),
                calories=steps_data.get('totalKilocalories'),
                floorsClimbed=steps_data.get('totalFloorsClimbed'),
                minutesModerateIntensity=steps_data.get('minutesModerateIntensity'),
                minutesVigorousIntensity=steps_data.get('minutesVigorousIntensity'),
                avgStressLevel=steps_data.get('avgStressLevel'),
                restingHeartRate=steps_data.get('restingHeartRate')
            )
            
            logger.info(f"Retrieved daily steps for {date_str}: {daily_steps.steps} steps")
            return daily_steps
            
        except Exception as e:
            logger.error(f"Failed to get daily steps for {date}: {str(e)}")
            raise Exception(f"Failed to get daily steps: {str(e)}")
    
    async def get_daily_summary(self, token: str, date: datetime) -> DailySummary:
        """
        Get comprehensive daily summary including sleep, stress, etc.
        """
        garmin_client = self.get_client(token)
        if not garmin_client:
            raise Exception("Invalid or expired token")
        
        try:
            date_str = date.strftime('%Y-%m-%d')
            
            # Get steps data
            steps = await self.get_daily_steps(token, date)
            
            # Get additional data - check if methods are async
            try:
                sleep_data = await garmin_client.get_sleep_data(date_str)
                stress_data = await garmin_client.get_stress_data(date_str)
                body_battery_data = await garmin_client.get_body_battery(date_str)
            except TypeError:
                # If not async, try sync
                sleep_data = garmin_client.get_sleep_data(date_str)
                stress_data = garmin_client.get_stress_data(date_str)
                body_battery_data = garmin_client.get_body_battery(date_str)
            
            daily_summary = DailySummary(
                date=date,
                steps=steps,
                restingHeartRate=steps.restingHeartRate,
                sleep=sleep_data,
                stress=stress_data,
                bodyBattery=body_battery_data
            )
            
            logger.info(f"Retrieved daily summary for {date_str}")
            return daily_summary
            
        except Exception as e:
            logger.error(f"Failed to get daily summary for {date}: {str(e)}")
            raise Exception(f"Failed to get daily summary: {str(e)}")
    
    async def get_health_metrics(self, token: str, date: datetime, user_id: str) -> HealthMetrics:
        """
        Get comprehensive health metrics for a specific date
        """
        garmin_client = self.get_client(token)
        if not garmin_client:
            raise Exception("Invalid or expired token")
        
        try:
            date_str = date.strftime('%Y-%m-%d')
            
            # Initialize health metrics
            health_metrics = HealthMetrics(date=date)
            
            # Get basic health data
            try:
                # Heart rate data
                heart_rate_data = await self._get_heart_rate_data(garmin_client, date_str)
                if heart_rate_data:
                    health_metrics.restingHeartRate = heart_rate_data.get('restingHeartRate')
                    health_metrics.maxHeartRate = heart_rate_data.get('maxHeartRate')
                    health_metrics.avgHeartRate = heart_rate_data.get('avgHeartRate')
                
                # HRV data
                hrv_data = await self._get_hrv_data(garmin_client, date_str)
                if hrv_data:
                    health_metrics.hrv = hrv_data
                
                # Stress data
                stress_data = await self._get_stress_data(garmin_client, date_str)
                if stress_data:
                    health_metrics.stress = stress_data
                
                # Sleep data
                sleep_data = await self._get_sleep_data(garmin_client, date_str)
                if sleep_data:
                    health_metrics.sleep = sleep_data
                
                # Body Battery data
                body_battery_data = await self._get_body_battery_data(garmin_client, date_str)
                if body_battery_data:
                    health_metrics.bodyBattery = body_battery_data
                
                # SpO2 data
                spo2_data = await self._get_spo2_data(garmin_client, date_str)
                if spo2_data:
                    health_metrics.spo2 = spo2_data.get('avgSpO2')
                
                # Weight and body composition
                weight_data = await self._get_weight_data(garmin_client, date_str)
                if weight_data:
                    health_metrics.weight = weight_data.get('weight')
                    health_metrics.bodyFat = weight_data.get('bodyFat')
                    health_metrics.bodyMassIndex = weight_data.get('bmi')
                    health_metrics.muscleMass = weight_data.get('muscleMass')
                    health_metrics.boneMass = weight_data.get('boneMass')
                    health_metrics.bodyWater = weight_data.get('bodyWater')
                    health_metrics.visceralFat = weight_data.get('visceralFat')
                
                # Hydration
                hydration_data = await self._get_hydration_data(garmin_client, date_str)
                if hydration_data:
                    health_metrics.hydration = hydration_data.get('hydration')
                
                # VO2 Max
                vo2_max_data = await self._get_vo2_max_data(garmin_client)
                if vo2_max_data:
                    health_metrics.vo2Max = vo2_max_data.get('vo2Max')
                
                # Training Readiness
                training_readiness_data = await self._get_training_readiness_data(garmin_client, date_str)
                if training_readiness_data:
                    health_metrics.trainingReadiness = training_readiness_data
                
                # Respiration
                respiration_data = await self._get_respiration_data(garmin_client, date_str)
                if respiration_data:
                    health_metrics.respiration = respiration_data
                
                # Pulse Ox
                pulse_ox_data = await self._get_pulse_ox_data(garmin_client, date_str)
                if pulse_ox_data:
                    health_metrics.pulseOx = pulse_ox_data
                
                # Activity metrics - steps and calories
                steps_data = await self._get_steps_data(garmin_client, date_str)
                if steps_data:
                    health_metrics.steps = steps_data.get('totalSteps')
                    health_metrics.calories = steps_data.get('totalKilocalories')
                    
            except Exception as e:
                logger.error(f"Error getting health metrics for {date_str}: {str(e)}")
                # Continue with partial data
            
            logger.info(f"Retrieved health metrics for {date_str}")
            return health_metrics
            
        except Exception as e:
            logger.error(f"Failed to get health metrics for {date}: {str(e)}")
            raise Exception(f"Failed to get health metrics: {str(e)}")
    
    async def get_advanced_health_metrics(self, token: str, date: datetime, user_id: str) -> AdvancedHealthMetrics:
        """
        Get advanced health metrics including detailed breakdowns
        """
        garmin_client = self.get_client(token)
        if not garmin_client:
            raise Exception("Invalid or expired token")
        
        try:
            date_str = date.strftime('%Y-%m-%d')
            
            # Initialize advanced health metrics
            advanced_metrics = AdvancedHealthMetrics(date=date)
            
            # Get detailed health data
            try:
                # Detailed sleep data
                sleep_details = await self._get_detailed_sleep_data(garmin_client, date_str)
                if sleep_details:
                    advanced_metrics.sleepDetails = sleep_details
                
                # Detailed stress data
                stress_details = await self._get_detailed_stress_data(garmin_client, date_str)
                if stress_details:
                    advanced_metrics.stressDetails = stress_details
                
                # Detailed HRV data
                hrv_details = await self._get_detailed_hrv_data(garmin_client, date_str)
                if hrv_details:
                    advanced_metrics.hrvDetails = hrv_details
                
                # Detailed Body Battery data
                body_battery_details = await self._get_detailed_body_battery_data(garmin_client, date_str)
                if body_battery_details:
                    advanced_metrics.bodyBatteryDetails = body_battery_details
                
                # Detailed Training Readiness data
                training_readiness_details = await self._get_detailed_training_readiness_data(garmin_client, date_str)
                if training_readiness_details:
                    advanced_metrics.trainingReadinessDetails = training_readiness_details
                
                # Wellness data
                wellness_data = await self._get_wellness_data(garmin_client, date_str)
                if wellness_data:
                    advanced_metrics.wellnessData = wellness_data
                
                # Health Snapshot
                health_snapshot = await self._get_health_snapshot(garmin_client, date_str)
                if health_snapshot:
                    advanced_metrics.healthSnapshot = health_snapshot
                    
            except Exception as e:
                logger.error(f"Error getting advanced health metrics for {date_str}: {str(e)}")
                # Continue with partial data
            
            logger.info(f"Retrieved advanced health metrics for {date_str}")
            return advanced_metrics
            
        except Exception as e:
            logger.error(f"Failed to get advanced health metrics for {date}: {str(e)}")
            raise Exception(f"Failed to get advanced health metrics: {str(e)}")
    
    async def get_daily_metrics(self, token: str, date: datetime, user_id: str) -> DailyMetrics:
        """
        Get complete daily metrics including both basic and advanced health metrics
        """
        try:
            # Get basic health metrics
            health_metrics = await self.get_health_metrics(token, date, user_id)
            
            # Get advanced health metrics
            advanced_metrics = await self.get_advanced_health_metrics(token, date, user_id)
            
            # Create daily metrics
            daily_metrics = DailyMetrics(
                date=date,
                userId=user_id,
                healthMetrics=health_metrics,
                advancedMetrics=advanced_metrics,
                syncedAt=datetime.now()
            )
            
            logger.info(f"Retrieved complete daily metrics for {date.strftime('%Y-%m-%d')}")
            return daily_metrics
            
        except Exception as e:
            logger.error(f"Failed to get daily metrics for {date}: {str(e)}")
            raise Exception(f"Failed to get daily metrics: {str(e)}")
    
    async def sync_health_metrics(self, token: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, user_id: str = "unknown") -> HealthMetricsSyncResponse:
        """
        Synchronize health metrics for a date range with optimized processing
        """
        errors = []
        synced_days = 0
        total_days = 0
        
        try:
            # Set default dates if not provided (last 7 days for health metrics)
            if not start_date:
                start_date = datetime.now() - timedelta(days=7)
            if not end_date:
                end_date = datetime.now()
            
            # Calculate total days for progress tracking
            total_days = (end_date - start_date).days + 1
            logger.info(f"Starting health metrics sync for user {user_id}: {total_days} days from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
            
            current_date = start_date
            day_count = 0
            
            while current_date <= end_date:
                day_count += 1
                date_str = current_date.strftime('%Y-%m-%d')
                
                try:
                    logger.info(f"Syncing health metrics for day {day_count}/{total_days}: {date_str}")
                    
                    # Get daily metrics with individual error handling for each metric type
                    await self.get_daily_metrics(token, current_date, user_id)
                    synced_days += 1
                    logger.info(f"Successfully synced health metrics for {date_str} ({day_count}/{total_days})")
                    
                except Exception as e:
                    error_msg = f"Failed to sync health metrics for {date_str} ({day_count}/{total_days}): {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
                    
                    # Continue with next day even if current day fails
                    logger.warning(f"Continuing with next day despite error for {date_str}")
                
                current_date += timedelta(days=1)
            
            # Log final results
            success_rate = (synced_days / total_days * 100) if total_days > 0 else 0
            logger.info(f"Health metrics sync completed for user {user_id}: {synced_days}/{total_days} days synced ({success_rate:.1f}% success rate)")
            
            if errors:
                logger.warning(f"Encountered {len(errors)} errors during sync for user {user_id}")
                for error in errors[-5:]:  # Log last 5 errors to avoid spam
                    logger.warning(f"Error: {error}")
            
            return HealthMetricsSyncResponse(
                success=len(errors) == 0,
                synced_days=synced_days,
                errors=errors,
                last_sync_time=datetime.now(),
                metrics_type="basic"
            )
            
        except Exception as e:
            error_msg = f"Health metrics sync failed for user {user_id}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            
            return HealthMetricsSyncResponse(
                success=False,
                synced_days=synced_days,
                errors=errors,
                last_sync_time=datetime.now(),
                metrics_type="basic"
            )
    
    async def sync_user_data(self, token: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> SyncResponse:
        """
        Synchronize all user data (activities and daily summaries)
        """
        errors = []
        synced_activities = 0
        synced_days = 0
        
        try:
            # Sync activities
            activities = await self.get_activities(token, start_date, end_date)
            synced_activities = len(activities)
            
            # Sync daily summaries
            if start_date and end_date:
                current_date = start_date
                while current_date <= end_date:
                    try:
                        await self.get_daily_summary(token, current_date)
                        synced_days += 1
                    except Exception as e:
                        errors.append(f"Failed to sync daily summary for {current_date}: {str(e)}")
                    
                    current_date += timedelta(days=1)
            
            return SyncResponse(
                success=True,
                synced_activities=synced_activities,
                synced_days=synced_days,
                errors=errors,
                last_sync_time=datetime.now()
            )
            
        except Exception as e:
            errors.append(f"Sync failed: {str(e)}")
            return SyncResponse(
                success=False,
                synced_activities=synced_activities,
                synced_days=synced_days,
                errors=errors
            )
    
    def logout(self, token: str) -> bool:
        """Logout and remove session"""
        if token in self.active_sessions:
            del self.active_sessions[token]
            logger.info(f"User logged out successfully")
            return True
        return False
    
    # Helper methods for getting specific health data
    async def _get_heart_rate_data(self, garmin_client: Garmin, date_str: str) -> Optional[Dict[str, Any]]:
        """Get heart rate data"""
        try:
            if hasattr(garmin_client, 'get_heart_rates'):
                try:
                    data = await garmin_client.get_heart_rates(date_str)
                except TypeError:
                    data = garmin_client.get_heart_rates(date_str)
                return data
        except Exception as e:
            logger.warning(f"Failed to get heart rate data for {date_str}: {str(e)}")
        return None
    
    async def _get_hrv_data(self, garmin_client: Garmin, date_str: str) -> Optional[Dict[str, Any]]:
        """Get HRV data"""
        try:
            if hasattr(garmin_client, 'get_hrv_data'):
                try:
                    data = await garmin_client.get_hrv_data(date_str)
                except TypeError:
                    data = garmin_client.get_hrv_data(date_str)
                return data
        except Exception as e:
            logger.warning(f"Failed to get HRV data for {date_str}: {str(e)}")
        return None
    
    async def _get_stress_data(self, garmin_client: Garmin, date_str: str) -> Optional[Dict[str, Any]]:
        """Get stress data"""
        try:
            if hasattr(garmin_client, 'get_stress_data'):
                try:
                    data = await garmin_client.get_stress_data(date_str)
                except TypeError:
                    data = garmin_client.get_stress_data(date_str)
                return data
        except Exception as e:
            logger.warning(f"Failed to get stress data for {date_str}: {str(e)}")
        return None
    
    async def _get_sleep_data(self, garmin_client: Garmin, date_str: str) -> Optional[Dict[str, Any]]:
        """Get sleep data"""
        try:
            if hasattr(garmin_client, 'get_sleep_data'):
                try:
                    data = await garmin_client.get_sleep_data(date_str)
                except TypeError:
                    data = garmin_client.get_sleep_data(date_str)
                return data
        except Exception as e:
            logger.warning(f"Failed to get sleep data for {date_str}: {str(e)}")
        return None
    
    async def _get_body_battery_data(self, garmin_client: Garmin, date_str: str) -> Optional[Dict[str, Any]]:
        """Get body battery data"""
        try:
            if hasattr(garmin_client, 'get_body_battery'):
                try:
                    data = await garmin_client.get_body_battery(date_str)
                except TypeError:
                    data = garmin_client.get_body_battery(date_str)
                return data
        except Exception as e:
            logger.warning(f"Failed to get body battery data for {date_str}: {str(e)}")
        return None
    
    async def _get_spo2_data(self, garmin_client: Garmin, date_str: str) -> Optional[Dict[str, Any]]:
        """Get SpO2 data"""
        try:
            if hasattr(garmin_client, 'get_pulse_ox'):
                try:
                    data = await garmin_client.get_pulse_ox(date_str)
                except TypeError:
                    data = garmin_client.get_pulse_ox(date_str)
                return data
        except Exception as e:
            logger.warning(f"Failed to get SpO2 data for {date_str}: {str(e)}")
        return None
    
    async def _get_weight_data(self, garmin_client: Garmin, date_str: str) -> Optional[Dict[str, Any]]:
        """Get weight and body composition data"""
        try:
            if hasattr(garmin_client, 'get_body_composition'):
                try:
                    data = await garmin_client.get_body_composition(date_str)
                except TypeError:
                    data = garmin_client.get_body_composition(date_str)
                return data
        except Exception as e:
            logger.warning(f"Failed to get weight data for {date_str}: {str(e)}")
        return None
    
    async def _get_hydration_data(self, garmin_client: Garmin, date_str: str) -> Optional[Dict[str, Any]]:
        """Get hydration data"""
        try:
            if hasattr(garmin_client, 'get_hydration_data'):
                try:
                    data = await garmin_client.get_hydration_data(date_str)
                except TypeError:
                    data = garmin_client.get_hydration_data(date_str)
                return data
        except Exception as e:
            logger.warning(f"Failed to get hydration data for {date_str}: {str(e)}")
        return None
    
    async def _get_vo2_max_data(self, garmin_client: Garmin) -> Optional[Dict[str, Any]]:
        """Get VO2 Max data"""
        try:
            if hasattr(garmin_client, 'get_user_summary'):
                try:
                    data = await garmin_client.get_user_summary()
                except TypeError:
                    data = garmin_client.get_user_summary()
                return data
        except Exception as e:
            logger.warning(f"Failed to get VO2 Max data: {str(e)}")
        return None
    
    async def _get_training_readiness_data(self, garmin_client: Garmin, date_str: str) -> Optional[Dict[str, Any]]:
        """Get training readiness data"""
        try:
            if hasattr(garmin_client, 'get_training_readiness'):
                try:
                    data = await garmin_client.get_training_readiness(date_str)
                except TypeError:
                    data = garmin_client.get_training_readiness(date_str)
                return data
        except Exception as e:
            logger.warning(f"Failed to get training readiness data for {date_str}: {str(e)}")
        return None
    
    async def _get_respiration_data(self, garmin_client: Garmin, date_str: str) -> Optional[Dict[str, Any]]:
        """Get respiration data"""
        try:
            if hasattr(garmin_client, 'get_respiration_data'):
                try:
                    data = await garmin_client.get_respiration_data(date_str)
                except TypeError:
                    data = garmin_client.get_respiration_data(date_str)
                return data
        except Exception as e:
            logger.warning(f"Failed to get respiration data for {date_str}: {str(e)}")
        return None
    
    async def _get_pulse_ox_data(self, garmin_client: Garmin, date_str: str) -> Optional[Dict[str, Any]]:
        """Get pulse ox data"""
        try:
            if hasattr(garmin_client, 'get_pulse_ox_detailed'):
                try:
                    data = await garmin_client.get_pulse_ox_detailed(date_str)
                except TypeError:
                    data = garmin_client.get_pulse_ox_detailed(date_str)
                return data
        except Exception as e:
            logger.warning(f"Failed to get pulse ox data for {date_str}: {str(e)}")
        return None
    
    # Advanced data helper methods
    async def _get_detailed_sleep_data(self, garmin_client: Garmin, date_str: str) -> Optional[Dict[str, Any]]:
        """Get detailed sleep data"""
        try:
            if hasattr(garmin_client, 'get_sleep_summary'):
                try:
                    data = await garmin_client.get_sleep_summary(date_str)
                except TypeError:
                    data = garmin_client.get_sleep_summary(date_str)
                return data
        except Exception as e:
            logger.warning(f"Failed to get detailed sleep data for {date_str}: {str(e)}")
        return None
    
    async def _get_detailed_stress_data(self, garmin_client: Garmin, date_str: str) -> Optional[Dict[str, Any]]:
        """Get detailed stress data"""
        try:
            if hasattr(garmin_client, 'get_stress_levels'):
                try:
                    data = await garmin_client.get_stress_levels(date_str)
                except TypeError:
                    data = garmin_client.get_stress_levels(date_str)
                return data
        except Exception as e:
            logger.warning(f"Failed to get detailed stress data for {date_str}: {str(e)}")
        return None
    
    async def _get_detailed_hrv_data(self, garmin_client: Garmin, date_str: str) -> Optional[Dict[str, Any]]:
        """Get detailed HRV data"""
        try:
            if hasattr(garmin_client, 'get_hrv_summary'):
                try:
                    data = await garmin_client.get_hrv_summary(date_str)
                except TypeError:
                    data = garmin_client.get_hrv_summary(date_str)
                return data
        except Exception as e:
            logger.warning(f"Failed to get detailed HRV data for {date_str}: {str(e)}")
        return None
    
    async def _get_detailed_body_battery_data(self, garmin_client: Garmin, date_str: str) -> Optional[Dict[str, Any]]:
        """Get detailed body battery data"""
        try:
            if hasattr(garmin_client, 'get_body_battery_summary'):
                try:
                    data = await garmin_client.get_body_battery_summary(date_str)
                except TypeError:
                    data = garmin_client.get_body_battery_summary(date_str)
                return data
        except Exception as e:
            logger.warning(f"Failed to get detailed body battery data for {date_str}: {str(e)}")
        return None
    
    async def _get_detailed_training_readiness_data(self, garmin_client: Garmin, date_str: str) -> Optional[Dict[str, Any]]:
        """Get detailed training readiness data"""
        try:
            if hasattr(garmin_client, 'get_training_readiness_detailed'):
                try:
                    data = await garmin_client.get_training_readiness_detailed(date_str)
                except TypeError:
                    data = garmin_client.get_training_readiness_detailed(date_str)
                return data
        except Exception as e:
            logger.warning(f"Failed to get detailed training readiness data for {date_str}: {str(e)}")
        return None
    
    async def _get_wellness_data(self, garmin_client: Garmin, date_str: str) -> Optional[Dict[str, Any]]:
        """Get wellness data"""
        try:
            if hasattr(garmin_client, 'get_daily_wellness'):
                try:
                    data = await garmin_client.get_daily_wellness(date_str)
                except TypeError:
                    data = garmin_client.get_daily_wellness(date_str)
                return data
        except Exception as e:
            logger.warning(f"Failed to get wellness data for {date_str}: {str(e)}")
        return None
    
    async def _get_steps_data(self, garmin_client: Garmin, date_str: str) -> Optional[Dict[str, Any]]:
        """Get steps data including calories"""
        try:
            # Try multiple methods to get steps and calories data
            
            # Method 1: Try get_user_daily_summary (most comprehensive)
            if hasattr(garmin_client, 'get_user_daily_summary'):
                try:
                    data = await garmin_client.get_user_daily_summary(date_str)
                except TypeError:
                    data = garmin_client.get_user_daily_summary(date_str)
                
                if data:
                    steps_data = {
                        'totalSteps': data.get('totalSteps', 0),
                        'totalKilocalories': data.get('totalKilocalories', 0),
                        'totalDistance': data.get('totalDistance', 0),
                        'calories': data.get('totalKilocalories', 0)
                    }
                    logger.info(f"Got steps data from user_daily_summary: {steps_data}")
                    return steps_data
            
            # Method 2: Try get_daily_summary
            if hasattr(garmin_client, 'get_daily_summary'):
                try:
                    data = await garmin_client.get_daily_summary(date_str)
                except TypeError:
                    data = garmin_client.get_daily_summary(date_str)
                
                if data:
                    steps_data = {
                        'totalSteps': data.get('totalSteps', 0),
                        'totalKilocalories': data.get('totalKilocalories', 0),
                        'totalDistance': data.get('totalDistance', 0),
                        'calories': data.get('totalKilocalories', 0)
                    }
                    logger.info(f"Got steps data from daily_summary: {steps_data}")
                    return steps_data
            
            # Method 3: Try get_steps_data (specific steps method)
            if hasattr(garmin_client, 'get_steps_data'):
                try:
                    data = await garmin_client.get_steps_data(date_str)
                except TypeError:
                    data = garmin_client.get_steps_data(date_str)
                
                if data:
                    steps_data = {
                        'totalSteps': data.get('totalSteps', 0),
                        'totalKilocalories': data.get('totalKilocalories', 0),
                        'totalDistance': data.get('totalDistance', 0),
                        'calories': data.get('totalKilocalories', 0)
                    }
                    logger.info(f"Got steps data from steps_data: {steps_data}")
                    return steps_data
            
            # Method 4: Try get_activities and sum steps/calories from activities
            if hasattr(garmin_client, 'get_activities_by_date'):
                try:
                    activities = await garmin_client.get_activities_by_date(date_str, date_str)
                except TypeError:
                    activities = garmin_client.get_activities_by_date(date_str, date_str)
                
                if activities:
                    total_steps = sum(activity.get('steps', 0) for activity in activities if activity.get('steps'))
                    total_calories = sum(activity.get('calories', 0) for activity in activities if activity.get('calories'))
                    
                    steps_data = {
                        'totalSteps': total_steps,
                        'totalKilocalories': total_calories,
                        'totalDistance': 0,
                        'calories': total_calories
                    }
                    logger.info(f"Got steps data from activities: {steps_data}")
                    return steps_data
            
            logger.warning(f"No steps data found for {date_str}")
            return None
                
        except Exception as e:
            logger.warning(f"Failed to get steps data for {date_str}: {str(e)}")
        return None
    
    async def _get_health_snapshot(self, garmin_client: Garmin, date_str: str) -> Optional[Dict[str, Any]]:
        """Get health snapshot data"""
        try:
            if hasattr(garmin_client, 'get_health_snapshot'):
                try:
                    data = await garmin_client.get_health_snapshot(date_str)
                except TypeError:
                    data = garmin_client.get_health_snapshot(date_str)
                return data
        except Exception as e:
            logger.warning(f"Failed to get health snapshot for {date_str}: {str(e)}")
        return None

# Global service instance
garmin_service = GarminService()

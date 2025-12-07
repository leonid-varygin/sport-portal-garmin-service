import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    API_KEY: str = os.getenv("API_KEY", "garmin-service-secret-key")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Garmin settings
    GARMIN_TIMEOUT: int = int(os.getenv("GARMIN_TIMEOUT", "30"))

settings = Settings()

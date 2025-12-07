import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
from .config import settings
from .routes import auth, activities, daily, health_metrics

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Garmin Service starting up...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"API Host: {settings.API_HOST}")
    logger.info(f"API Port: {settings.API_PORT}")
    yield
    # Shutdown
    logger.info("Garmin Service shutting down...")

# Create FastAPI app
app = FastAPI(
    title="Garmin Connect Service",
    description="Microservice for Garmin Connect API integration",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Include routers
app.include_router(auth.router)
app.include_router(activities.router)
app.include_router(daily.router)
app.include_router(health_metrics.router)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "garmin-connect-service",
        "timestamp": time.time(),
        "environment": settings.ENVIRONMENT
    }

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "Garmin Connect Service",
        "version": "1.0.0",
        "description": "Microservice for Garmin Connect API integration",
        "endpoints": {
            "auth": "/auth",
            "activities": "/activities",
            "daily": "/daily",
            "health-metrics": "/health-metrics",
            "health": "/health",
            "docs": "/docs"
        }
    }

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.ENVIRONMENT == "development" else "Something went wrong"
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.ENVIRONMENT == "development",
        log_level=settings.LOG_LEVEL.lower()
    )

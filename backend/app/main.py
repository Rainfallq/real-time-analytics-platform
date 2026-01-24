from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import time
import logging


from app.core.config import settings
from app.api.router import api_router
from app.db.session import engine
from app.db.base import Base


logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


app = FastAPI(
    title="Real Time Analytics Platform",
    vesrion=settings.APP_VERSION,
    description="High-Performance Real-Time Analytics Platform",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    )

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Trusted host 
if not settings.DEBUG:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]
    )

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Global excpetion handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global excpetion: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "path": str(request.url)
        }
    )

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Starting Real-Time Analytics Platform...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    
    logger.info("✅ Application started successfuly")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 Shutting down Real-Time Analytics Platform...")
    await engine.dispose()
    logger.info("✅ Shutdown complete")

# Include api router
app.include_router(api_router, prefix="/api")

# Root endpoint
@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "environment": settings.ENVIRONMENT,
        "docs": "/docs" if settings.DEBUG else "disabled"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }

# # Readiness probe (for Kubernetes)
# @app.get("/ready")
# async def readiness_probe():
#     """Readiness probe - checks if app is ready to serve traffic"""
#     # Add checks for database, redis, etc.
#     try:
#         # Quick DB check
#         async with engine.connect() as conn:
#             await conn.execute("SELECT 1")
#         return {"status": "ready"}
#     except Exception as e:
#         logger.error(f"Readiness check failed: {e}")
#         return JSONResponse(
#             status_code=503,
#             content={"status": "not ready", "error": str(e)}
#         )

# # Liveness probe (for Kubernetes)
# @app.get("/alive")
# async def liveness_probe():
#     """Liveness probe - checks if app is alive"""
#     return {"status": "alive"}

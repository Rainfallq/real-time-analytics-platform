from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import time
import logging


from app.core.config import settings
from app.api.router import api_router
from app.db.session import engine, get_db
from app.core.metrics import DB_POOL_CHECKED_OUT, DB_POOL_SIZE
from app.core.metrics_middleware import PrometheusMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import Base


logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _pool_checked_out() -> float:
    try:
        return float(engine.pool.checkedout())
    except Exception:
        return 0.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Real-Time Analytics Platform")
    logger.info("Environment: %s, debug: %s, ingest mode: %s",
                settings.ENVIRONMENT, settings.DEBUG, settings.INGEST_MODE)
    DB_POOL_SIZE.set(settings.DATABASE_POOL_SIZE)
    DB_POOL_CHECKED_OUT.set_function(_pool_checked_out)
    yield
    logger.info("Shutting down Real-Time Analytics Platform")
    await engine.dispose()
    logger.info("Shutdown complete")


app = FastAPI(
    lifespan=lifespan,
    title="Real Time Analytics Platform",
    version=settings.APP_VERSION,
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

# Prometheus request metrics
app.add_middleware(PrometheusMiddleware, router=app)

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

@app.get("/alive")
async def liveness_probe():
    """Liveness probe. It makes no external calls on purpose, so a database
    outage does not make Kubernetes restart healthy pods."""
    return {"status": "alive"}


@app.get("/ready")
async def readiness_probe(db: AsyncSession = Depends(get_db)):
    """Readiness probe. The pod receives traffic only if the database answers."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:
        logger.error("Readiness check failed: %s", exc)
        return JSONResponse(status_code=503, content={"status": "not ready"})


@app.get("/metrics", include_in_schema=False)
async def metrics():
    """Prometheus metrics."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

"""
Docstring for backend.app.api.v1.router
API V1 Router
Includes all v1 endpoints
"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, events, analytics

# V1 Router
router = APIRouter()

# Include endpoint routers
router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(events.router, prefix="/events", tags=["Events"])
router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])


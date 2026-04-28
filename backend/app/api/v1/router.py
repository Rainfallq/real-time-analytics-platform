"""
Docstring for backend.app.api.v1.router
API V1 Router
Includes all v1 endpoints
"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, analytics, transaction

# V1 Router
router = APIRouter()

# Include endpoint routers
router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
router.include_router(transaction.router, prefix="/transactions", tags=["Transactions"])



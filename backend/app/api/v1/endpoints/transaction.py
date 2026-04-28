from fastapi import APIRouter, status, Depends, BackgroundTasks, HTTPException
from app.api.v1.schemas.transaction import (
    TransactionCreate,
    TransactionBatchCreate,
    TransactionResponse,
    TransactionListResponse,
    TransactionStatsResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, get_current_active_user
from app.models.user import User
from app.models.transaction import Transaction
from app.core.config import settings
from datetime import datetime, timezone, timedelta
from uuid import UUID
from sqlalchemy import select, func, and_, desc
from decimal import Decimal
import time

from app.services.transaction_service import TransactionService



router = APIRouter()


@router.post(
    '/ingest',
    response_model=TransactionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest single transaction"
)
async def ingest_transaction(
    transaction_data: TransactionCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Ingest a single financial transaction
    """
    service = TransactionService(db)
    return await service.create_transaction(transaction_data)


@router.post(
    '/batch',
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest 1000 transactions batch"
)
async def ingest_batch(
    batch_data: TransactionBatchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = TransactionService(db)
    return await service.create_batch(batch_data.transactions)


@router.get(
    '/',
    response_model=TransactionListResponse,
    summary="List transactions"
)
async def list_transactions(
    transaction_type: str | None = None,
    merchant_id: UUID | None = None,
    customer_id: UUID | None = None,
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    is_fraud: bool | None = None,
    min_fraud_score: float | None = None,
    status_filter: str| None = None,
    limit: int = 1000,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = TransactionService(db)
    transactions, total = await service.list_transactions(
        transaction_type=transaction_type,
        customer_id=customer_id,
        merchant_id=merchant_id,
        start_time=start_time,
        end_time=end_time,
        min_amount=min_amount,
        max_amount=max_amount,
        is_fraud=is_fraud,
        min_fraud_score=min_fraud_score,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )
    return {
        "transactions": transactions,
        "total": total,
        "limit": limit,
        "offset": offset
        }


@router.get(
    "/stats/summary",
    response_model=TransactionStatsResponse,
    summary="Get transaction statistics"
)
async def get_summary_stats(
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user) 
):
    service = TransactionService(db)
    return await service.get_summary_stats(hours)


@router.get(
    "/{transaction_id}",
    response_model=TransactionResponse,
    summary="Get transaction by ID"
)
async def get_transaction(
    transaction_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a single transaction by its external transaction_id"""
    service = TransactionService(db)
    return await service.get_transaction(transaction_id)
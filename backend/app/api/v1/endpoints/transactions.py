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
    
    - High-performance endpoint optimized for low latency
    - Returns 202 Accepted immediately
    - Processing happens asynchronously
    - Future: Will send to Kafka for stream processing
    """
    start_time = time.time()

    existing = await db.execute(
        select(Transaction).where(Transaction.transaction_id == transaction_data.transaction_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Transaction {transaction_data.transaction_id} already exists"
        )

    new_transaction = Transaction(**transaction_data.model_dump(), status="pending")
    
    db.add(new_transaction)
    await db.commit()
    await db.refresh(new_transaction)

    # TODO Phase 3: Send to Kafka for stream processing
    # background_tasks.add_task(send_to_kafka, new_transaction)

    processing_time = (time.time() - start_time) * 1000 # milliseconds
    new_transaction.processing_time_ms = processing_time
    await db.commit()

    return new_transaction
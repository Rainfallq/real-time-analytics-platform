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


@router.post(
    '/batch',
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a batch of 1000 transactions"
)
async def ingest_batch(
    batch_data: TransactionBatchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if len(batch_data.transactions) > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No more than 1000 transactions per batch"
        )

    transactions = []
    duplicate_count = 0

    for txn_data in batch_data.transactions:
        existing = await db.execute(
            select(Transaction).where(Transaction.transaction_id == txn_data.transaction_id)
        )
        if existing.scalar_one_or_none():
            duplicate_count += 1
            continue

        transaction = Transaction(**batch_data.model_dump(), status="pending")
        
        transactions.append(transaction)

    db.add_all(transactions)
    await db.commit()

    return {
        "accepted": len(transactions),
        "duplicates": duplicate_count,
        "status": "processing"
    }


@router.get(
    '/',
    response_model=TransactionResponse,
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

    query = select(Transaction)
    filters = []

    if transaction_type:
        filters.append(Transaction.transaction_type == transaction_type)
    if merchant_id: 
        filters.append(Transaction.merchant_id == merchant_id)
    if customer_id:
        filters.append(Transaction.customer_id == customer_id)
    if start_time:
        filters.append(Transaction.transaction_time >= start_time)
    if end_time:
        filters.append(Transaction.transaction_time <= end_time)
    if min_amount is not None:
        filters.append(Transaction.amount >= min_amount)
    if max_amount is not None:
        filters.append(Transaction.amount <= max_amount)
    if is_fraud is not None:
        filters.append(Transaction.is_fraud == is_fraud)
    if min_fraud_score is not None:
        filters.append(Transaction.fraud_score >= min_fraud_score)    
    if status_filter:
        filters.append(Transaction.status == status_filter)

    if filters:
        query = query.where(and_(*filters))

    query = query.order_by(desc(Transaction.transaction_time))
    query = query.limit(min(limit, 1000)).offset(offset)

    result = await db.execute(query)
    transactions = result.scalars().all()

    # Count total
    count_query = select(func.count()).select_from(Transaction)
    if filters:
        count_query = count_query.where(and_(*filters))

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    return {
        "transactions": transactions,
        "total": total,
        "limit": limit,
        "offset": offset
    }

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
    result = await db.execute(
        select(Transaction).where(Transaction.transaction_id == transaction_id)
    )
    transaction = result.scalar_one_or_none
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction {transaction_id} not found"
        )
    
    return transaction


@router.get(
    "/stats/summary",
    response_model=TransactionResponse,
    summary="Get transaction statistics"
)
async def get_summary_stats(
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user) 
):
    start_time = datetime.now(timezone.utc) - timedelta(hours=hours)

    count_result = await db.execute(
        select(
            func.count(Transaction.transaction_id),
            func.sum(Transaction.amount),
            func.avg(Transaction.amount),
            func.max(Transaction.amount),
        ).where(Transaction.transaction_time >= start_time)
    )

    total_count, total_amount, avg_amount, max_amount = count_result.one()

    total_count = total_count or 0
    total_sum = total_sum or Decimal(0)
    avg_amount = avg_amount or Decimal(0)
    max_amount = max_amount or Decimal(0)

    # By type
    type_result = await db.execute(
        select(Transaction.transaction_type, func.count())
        .where(Transaction.transaction_time >= start_time)
        .group_by(Transaction.transaction_type)
    )
    transactions_by_type = {row[0]: row[1] for row in type_result} 

    # By status
    status_result = await db.execute(
        select(Transaction.status, func.count())
        .where(Transaction.transaction_time >= start_time)
        .group_by(Transaction.status)
    )
    transactions_by_status = {row[0]: row[1] for row in status_result}

    # Fraud stats
    fraud_result = await db.execute(
        select(
            func.count(),
            func.avg(Transaction.fraud_score)
        ).where(
            and_(
                Transaction.transaction_time >= start_time,
                Transaction.is_fraud == True
            )
        )
    )
    fraud_count, avg_fraud_score = fraud_result.one()
    fraud_count = fraud_count or 0
    avg_fraud_score = float(avg_fraud_score) if avg_fraud_score else 0.0
    fraud_percentage = (fraud_count / total_count * 100) if total_count > 0 else 0.0

    return { 
        "time_range_hours": hours,
        "total_transactions": total_count,
        "total_amount": total_amount,
        "transaction_per_hour": round(total_count / hours, 2) if hours > 0 else 0,
        "transactions_by_type": transactions_by_type,
        "transactions_by_status": transactions_by_status,
        "fraud_count": fraud_count,
        "fraud_percentage": round(fraud_percentage, 2),
        "average_fraud_score": round(avg_fraud_score, 2),
        "average_amount": round(avg_amount, 2),
        "max_amount": max_amount,
        "top_merchants": [],
        "top_customers": []
        }


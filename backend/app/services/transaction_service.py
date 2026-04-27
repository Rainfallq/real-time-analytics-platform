from sqlalchemy.ext.asyncio import AsyncSession
import time
import logging
from sqlalchemy import select, func, and_, desc
from fastapi import HTTPException, status
from uuid import UUID
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from app.api.v1.schemas.transaction import TransactionCreate
from app.models.transaction import Transaction

logger = logging.getLogger(__name__)

class TransactionService:
    """
    Business logic for transaction processing.
 
    Responsibilities:
    - Create and validate transactions
    - Deduplication checks
    - Basic fraud scoring (rule-based, before ML)
    - Querying and filtering
    - Statistics aggregation
    """
    # DB Dependency Injection
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_transaction(self, txn_data: TransactionCreate) -> Transaction:
        """
        Create a single transaction.
 
        Steps:
        1. Idempotency check (duplicate transaction_id → 409)
        2. Build model instance
        3. Calculate basic fraud score
        4. Persist to DB
        5. Record processing time
        """
        start = time.perf_counter()

        # 1. Duplicate check
        if await self._is_duplicate(txn_data.transaction_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Transaction: '{txn_data.transaction_id}' already exists"
            )

        # 2. Build transaction model instance
        transaction = Transaction(
            **txn_data.model_dump(exclude={"fraud_score"}),
            status="pending",
            ) 
        
        # 3. Calculate basic fraud score
        transaction.fraud_score = await self._calculate_fraud_score(
            txn_data, transaction
        )
        if transaction.fraud_score >= 0.7:
            transaction.status = "flagged"
            transaction.fraud_reason = await self._build_fraud_reason(txn_data, transaction)

        # 4. Persist to DB
        self.db.add(transaction)
        await self.db.commit()
        await self.db.refresh(transaction)

        # 5. Record processing time
        transaction.processing_time_ms = (time.perf_counter() - start) * 1000
        await self.db.commit()

        logger.info(
            "Transaction ingested: id=%s amount=%s fraud_score=%.2f",
            transaction.transaction_id,
            transaction.amount,
            transaction.fraud_score or 0,
        )

        return transaction


    async def create_batch(
        self, txns_data: list[TransactionCreate]
        ) -> dict:
        incoming_ids = [t.transaction_id for t in txns_data]
        existing_result = await self.db.execute(
            select(Transaction.transaction_id).where(
                Transaction.transaction_id.in_(incoming_ids)
            )
        )
        existing_ids = set(existing_result.scalars().all())

        to_insert: list[Transaction] = []
        for txn_data in txns_data:
            if txn_data.transaction_id in existing_ids:
                continue

            transaction = Transaction(
                **txn_data.model_dump(), exclude={"fraud_score"},
                status="pending",
            )
            fraud_score = await self._calculate_fraud_score(txn_data, transaction)
            transaction.fraud_score = fraud_score
            if fraud_score >= 0.7:
                transaction.status = "flagged"
                transaction.fraud_reason = await self._build_fraud_reason(
                    txn_data, transaction
                    )
            to_insert.append(transaction)

        if to_insert:
            self.db.add_all(to_insert)
            await self.db.commit()

        logger.info(
            "Batch ingested: accepted=%d duplicates=%d",
            len(to_insert),
            len(existing_ids),
            )
        
        return {
            "accepted": len(to_insert),
            "duplicates": len(existing_ids),
            "status": "processing"
        }
    

    async def get_transaction(self, transaction_id: str) -> Transaction:
        """Get transaction by external transaction id"""
        result = await self.db.execute(select(Transaction).where(
            Transaction.transaction_id == transaction_id
            )
        )
        transaction = result.scalar_one_or_none()

        if transaction is None: 
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction: {transaction_id} not found",
            )
        return transaction
    
    
    async def list_transactions(
        self, 
        *,
        transaction_type: str | None = None,
        customer_id: UUID | None = None,
        merchant_id: UUID | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        min_amount: Decimal | None = None,
        max_amount: Decimal | None = None,
        is_fraud: bool | None = None,
        min_fraud_score: float | None = None,
        status_filter: str| None = None,
        limit: int = 100,
        offset: int = 0,
        ) -> tuple[list[Transaction], int]:
        """
        Returns a list of transactions and total count 
        matching the given filters
        """
        filters = self._build_filters(
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
        )
        query = select(Transaction)
        if filters:
            query = query.where(and_(*filters))
        query = query.order_by(desc(Transaction.transaction_time))
        query = query.limit(min(limit, 1000)).offset(offset)

        result = await self.db.execute(query)
        transactions = list(result.scalars().all())
        
        count_query = select(func.count()).select_from(Transaction)
        if filters:
            count_query = count_query.where(and_(*filters))
        total_count = (await self.db.execute(count_query)).scalar() or 0

        return transactions, total_count


    async def get_summary_stats(self, hours: int = 24) -> dict: 
        """
        Aggregate statistics for the last N hours
        """
        start_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        totals = (
            await self.db.execute(
                select(
                    func.count(Transaction.id),
                    func.sum(Transaction.amount),
                    func.avg(Transaction.amount),
                    func.max(Transaction.amount),
                ).where(Transaction.transaction_time >= start_time)
            )
        ).one()
        total_count, total_amount, avg_amount, max_amount = totals
        total_count = total_count or 0
        total_amount = total_amount or Decimal("0")
        avg_amount = avg_amount or Decimal("0")
        max_amount = max_amount or Decimal("0")
        
        # By type
        by_type = {
            row[0]: row[1] 
            for row in (
                await self.db.execute(
                    select(Transaction.transaction_type, func.count())
                    .where(Transaction.transaction_time >= start_time)
                    .group_by(Transaction.transaction_type)
                )
            )
        }
        
        # By status
        by_status = {
            row[0]: row[1]
            for row in (
                await self.db.execute(
                    select(Transaction.status, func.count())
                    .where(Transaction.transaction_time >= start_time)
                    .group_by(Transaction.status)
                )
            )
        }

        # Fraud stats
        fraud_row = (
            await self.db.execute(
                select(func.count(), func.avg(Transaction.fraud_score)).where(
                    and_(
                        Transaction.transaction_time >= start_time,
                        Transaction.is_fraud == True, # noqa: E712
                    )
                )
            )
        ).one()

        fraud_count = fraud_row[0] or 0
        avg_fraud_score = float(fraud_row[1]) if fraud_row[1] else 0.0
        fraud_percentage = (
            round(fraud_count / total_count * 100, 2) if total_count else 0.0 
        )

        return {
            "time_range_hours": hours,
            "total_transactions": total_count,
            "transaction_per_hour": round(total_count / hours, 2) if hours else 0.0,
            "total_amount": total_amount,
            "transactions_by_type": by_type,
            "transactions_by_status": by_status,
            "fraud_count": fraud_count,
            "fraud_percentage": fraud_percentage,
            "average_fraud_score": round(avg_fraud_score, 4),
            "average_amount": round(avg_amount, 2),
            "max_amount": max_amount,
            "top_merchants": [],
            "top_customers": [],
        }


    # Fraud scoring helpers
    async def _calculate_fraud_score(
        self, 
        txn_data: TransactionCreate, 
        transaction: Transaction,
        ) -> float:
        """
        Rule-based fraud score (0.0 – 1.0).
    
        Rules:
        +0.3  amount > $10 000
        +0.2  international transaction (country_code not US/None)
        +0.3  customer made >5 transactions in the last hour
        +0.1  round amount (multiple of 100, >= $500)
        +0.2  unusual hour (local 2-5 AM — approximated via UTC)
        +1.0  pre-labelled as fraud (override)
        """
        # Pre-labelled as fraud
        if txn_data.is_fraud: 
            return 1.0
        
        score = 0.0

        # Rule 1: Large amount
        if txn_data.amount > 10000:
            score += 0.3

        # Rule 2: Country code
        if txn_data.country_code and txn_data.country_code.upper() not in ("US", "USA"): 
            score += 0.2

        # Rule 3: Customer transaction count
        recent_count = self.get_customer_transaction_count(txn_data.customer_id, minutes=60) 
        if recent_count >= 5:
            score += 0.3

        # Rule 4: Round amount 
        if float(txn_data.amount) >= 500 and float(txn_data.amount) % 100 == 0: 
            score += 0.1

        # Rule 5: Unusual hour 
        txn_hour = (txn_data.transaction_time or datetime.now(timezone.utc)).hour
        if 2 <= txn_hour < 5: 
            score += 0.2

        return round(min(score, 1.0), 4)


    async def _build_fraud_reason(
        self,
        txn_data: TransactionCreate,
        transaction: Transaction, 
    ) -> str:
        """Fraud reason"""
        reasons: list[str] = []
        
        if txn_data.is_fraud:
            return "pre_labelled_fraud"
        
        if float(txn_data.amount) > 10000:
            reasons.append("large_amount")
        
        if txn_data.country_code and txn_data.country_code.upper() not in ("US", "USA"): 
            reasons.append("international")
        
        recent_count = await self.get_customer_transaction_count(
            txn_data.customer_id, minutes=60
        ) 
        if recent_count >= 5:
            reasons.append("high_velocity")

        if float(txn_data.amount) >= 500 and float(txn_data.amount) % 100 == 0: 
            reasons.append("round_amount")

        txn_hour = (txn_data.transaction_time or datetime.now(timezone.utc)).hour
        if 2 <= txn_hour < 5:
            reasons.append("unusual_hour")
        
        return " ,".join(reasons) if reasons else "rule_threshold"


    async def get_customer_transaction_count(
        self, 
        customer_id: UUID, 
        minutes: int = 60,
        ) -> int:
        """Count customer's transactions in the last N minutes"""
        since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        result = await self.db.execute(
            select(func.count()).select_from(Transaction).where(
                and_(
                    Transaction.customer_id == customer_id,
                    Transaction.transaction_time >= since,
                )
            )
        )   
        return result.scalar() or 0
                    

    # Internal helpers
    async def _is_duplicate(self, transaction_id: str) -> bool:
        """Check if the transaction is already in the database"""
        result = await self.db.execute(
            select(Transaction.transaction_id).where(
                Transaction.transaction_id == transaction_id
            )
        )
        return result.scalar_one_or_none() is not None
    
    
    def _build_filters(self, **kwargs) -> list:
        filters = []
        mapping = {
            "transaction_type": (Transaction.transaction_type, "__eq__"),
            "customer_id": (Transaction.customer_id, "__eq__"),
            "merchant_id": (Transaction.merchant_id, "__eq__"),
            "is_fraud": (Transaction.is_fraud, "__eq__"),
            "status_filter": (Transaction.status, "__eq__"),
        }
        range_mapping = {
            "start_time": (Transaction.transaction_time, "__ge__"),
            "end_time": (Transaction.transaction_time, "__le__"),
            "min_amount": (Transaction.amount, "__ge__"),
            "max_amount": (Transaction.amount, "__le__"),
            "min_fraud_score": (Transaction.fraud_score, "__ge__"),
        }
        for key, value in kwargs.items():
            if value is None: 
                continue
            if key in mapping:
                col, _ = mapping[key]
                filters.append(col==value)
            elif key in range_mapping:
                col, op = range_mapping[key]
                filters.append(getattr(col, op)(value))
        return filters 
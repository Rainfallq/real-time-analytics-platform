from app.db.base import Base, TimestampMixin
from sqlalchemy import Column, String, Numeric, DateTime, Boolean, Float, Integer, Index, text
import uuid
from sqlalchemy import Uuid, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from decimal import Decimal




class Transaction(Base, TimestampMixin):
    """
    Transaction model for real-time financial transaction monitoring
    
    Designed for:
    - High-throughput ingestion (10K+ txn/sec target)
    - Real-time fraud detection
    - Stream processing with Kafka
    - Time-series analytics with TimescaleDB
    """

    __tablename__ = "transactions"

    id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="Transaction id"
    )

    transaction_id = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="External transaction id (from payment system)"
    )

    amount = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        comment="Transaction amount"
    )

    currency = Column(
        String(3),
        nullable=False,
        default="USD",
        comment="Transaction currency (ISO 4217)"
    )

    transaction_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Transaction type: PAYMENT, TRANSFER, CASH_OUT, DEBIT, CASH_IN"
    )

    merchant_id = Column(
        Uuid(as_uuid=True),
        nullable=True,
        index=True,
        comment="Merchant UUID"
    )

    merchant_name = Column(
        String(255),
        nullable=True,
        comment="Merchant name"
    )
    
    customer_id = Column(
        Uuid(as_uuid=True),
        nullable=False,
        index=True,
        comment="Customer UUID"
    )

    card_number_hash = Column(
        String(128),
        nullable=True,
        comment="Hashed card number"
    )

    payment_method = Column(
        String(50),
        nullable=False,
        comment="CARD, BANK_TRANSFER, WALLET, CASH"
    )

    transaction_time = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When transaction occured"
    )

    ingested_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When transaction was ingested into system"
    )

    processed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When transaction was processed"
    )

    status = Column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="pending, approved, declined, flagged"
    )

    is_fraud = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Actual fraud label (if known)"
    )

    fraud_score = Column(
        Float,
        nullable=True,
        comment="ML fraud probability (0.0-1.0)"
    )

    fraud_reason = Column(
        String(255),
        nullable=True,
        comment="Reason for fraud flag"
    )

    risk_score = Column(
        Float,
        nullable=True,
        comment="Overall risk score (0.0-1.0)"
    )

    anomaly_score = Column(
        Float,
        nullable=True,
        comment="Anomaly detection score (0.0-1.0)"
    )

    country_code = Column(
        String(2),
        nullable=True,
        comment="ISO 3166-1 alpha-2 country code"
    )
    
    city = Column(
        String(100),
        nullable=True,
        comment="City name"
    )

    ip_address_hash = Column(
        String(128),
        nullable=True,
        comment="Hashed ip address"
    )

    transaction_metadata = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Additional transaction metadata"
    )

    processing_time_ms = Column(
        Float,
        nullable=True,
        comment="Time to process transaction (milliseconds)"
    )

    kafka_offset = Column(
        Integer,
        nullable=True,
        comment="Kafka offset (for stream processing)"
    )

    __table_args__ = (
        # Time based queries
        Index('ix_txn_time', 'transaction_time'),
        Index('ix_txn_customer_time', 'customer_id', 'transaction_time'),
        Index('ix_txn_merchant_time', 'merchant_id', 'transaction_time'),

        # Fraud related
        Index('ix_txn_fraud_time', 'is_fraud', 'transaction_time'),
        Index('ix_txn_fraud_score', 'fraud_score', postgresql_where=text("fraud_score > 0.7")),
        Index('ix_txn_status_time', 'status', 'transaction_time'),
        
        # Type queries
        Index('ix_txn_type_time', 'transaction_type', 'transaction_time'),

        # Amount queries
        Index('ix_txn_large_amount', 'amount', postgresql_where=text("amount > 1000")),

        # JSONB index 
        Index('ix_txn_metadata_gin', 'transaction_metadata', postgresql_using='gin'),

        # Unique constraint on external txn id
        Index('ix_txn_external_id', 'transaction_id', unique=True),
    )

    def __repr__(self):
        return f"<Transaction id={self.transaction_id!r} amount={self.amount} {self.currency} time={self.transaction_time}>"

    @property
    def latency_ms(self) -> float:
        if self.transaction_time and self.ingested_at:
            delta = self.ingested_at - self.transaction_time
            return delta.total_seconds() * 1000
        return 0.0

    @property
    def is_high_risk(self) -> bool:
        if self.fraud_score and self.fraud_score > 0.7:
            return True
        if self.risk_score and self.risk_score > 0.8:
            return True
        if self.amount and self.amount > Decimal("10000"):
            return True
        return False
        
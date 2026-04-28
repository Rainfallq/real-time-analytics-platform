
from pydantic import BaseModel, Field, ConfigDict, field_validator
from uuid import UUID
from decimal import Decimal
from datetime import datetime
from typing import Dict, Any, List



class TransactionCreate(BaseModel):
    """Schema for creating a new transaction"""
    transaction_id: str = Field(..., min_length=1, max_length=255)
    amount: Decimal = Field(..., max_digits=15, decimal_places=2, gt=0)
    currency: str = Field(..., default="USD", min_length=3, max_length=3)
    transaction_type: str = Field(...)

    merchant_id: UUID | None = Field(default=None)
    merchant_name: str | None = Field(default=None, max_length=255)
    customer_id: UUID = Field(...)
    
    card_number_hash: str | None = Field(default=None, max_length=128)
    payment_method: str = Field(..., max_length=50)
    
    transaction_time: datetime = Field(...)

    country_code: str | None = Field(default=None, max_length=2)
    city: str | None = Field(default=None, max_length=100)
    ip_address_hash: str | None = Field(default=None, max_length=128)

    transaction_metadata: Dict[str, Any] | None = Field(default={})
    
    is_fraud: bool = Field(default=False)  
    fraud_score: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("transaction_type")
    @classmethod
    def validate_transaction_type(cls, v):
        valid_types = ["PAYMENT", "TRANSFER", "CASH_OUT", "DEBIT", "CASH_IN"]
        if v.upper() not in valid_types:
            raise ValueError(f'Must be one of: {valid_types}')
        return v.upper()
    
    @field_validator("payment_method")
    @classmethod
    def validate_payment_method(cls, v):
        valid_methods = ["CARD", "BANK_TRANSFER", "WALLET", "CASH"]
        if v.upper() not in valid_methods:
            raise ValueError(f"Must be one of: {valid_methods}")
        return v.upper()
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "transaction_id": "txn_1234567890",
                "amount": 299.99,
                "currency": "USD",
                "transaction_type": "PAYMENT",
                "merchant_name": "Amazon.com",
                "customer_id": "987e6543-e21a-12d3-a456-426614174111",
                "payment_method": "CARD"
            }
        }
    )

class TransactionBatchCreate(BaseModel):
    """Schema for batch transaction ingestion"""
    transactions: List[TransactionCreate] = Field(..., min_length=1, max_length=1000)


class TransactionResponse(BaseModel):
    """Schema for transaction response"""
    id: UUID
    transaction_id: str
    amount: Decimal
    currency: str
    transaction_type: str
    
    merchant_id: UUID | None = Field(default=None)
    merchant_name: str | None = Field(default=None)
    customer_id: UUID
    
    payment_method: str
    
    transaction_time: datetime
    ingested_at: datetime
    processed_at: datetime | None = Field(default=None)
    
    status: str
    is_fraud: bool
    fraud_score: float | None = Field(default=None)
    
    country_code: str | None = Field(default=None)
    city: str | None = Field(default=None)
    
    transaction_metadata: Dict[str, Any]
    processing_time_ms: float | None = Field(default=None)
    
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransactionListResponse(BaseModel):
    """Paginated transaction list response"""
    transactions: List[TransactionResponse]
    total: int
    limit: int
    offset: int


class TransactionStatsResponse(BaseModel):
    """Transaction statistics response"""
    time_range_hours: int
    total_transactions: int
    total_amount: Decimal
    transactions_per_hour: float
    
    transactions_by_type: Dict[str, int]
    transactions_by_status: Dict[str, int]
    
    fraud_count: int
    fraud_percentage: float
    average_fraud_score: float
    
    average_amount: Decimal
    max_amount: Decimal
    
    top_merchants: List[Dict[str, Any]] = []
    top_customers: List[Dict[str, Any]] = []









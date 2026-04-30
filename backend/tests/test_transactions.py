"""
Tests for transaction endpoints and service layer.

Coverage:
- POST /api/v1/transactions/ingest
- POST /api/v1/transactions/batch
- GET  /api/v1/transactions/
- GET  /api/v1/transactions/{id}
- GET  /api/v1/transactions/stats/summary
- TransactionService unit tests
- Fraud scoring logic
"""
import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.transaction import Transaction
from app.services.transaction_service import TransactionService
from app.api.v1.schemas.transaction import TransactionCreate
from tests.conftest import make_transaction_payload

pytestmark = pytest.mark.asyncio



# POST /ingest


class TestIngest:

    async def test_ingest_success(
        self, client: AsyncClient, auth_headers: dict
    ):
        payload = make_transaction_payload()
        response = await client.post(
            "/api/v1/transactions/ingest",
            json=payload,
            headers=auth_headers,
        )
        assert response.status_code == 202
        data = response.json()
        assert data["transaction_id"] == payload["transaction_id"]
        assert data["status"] in ("pending", "flagged")
        assert "fraud_score" in data
        assert "id" in data

    async def test_ingest_duplicate_returns_409(
        self, client: AsyncClient, auth_headers: dict
    ):
        payload = make_transaction_payload()
        await client.post(
            "/api/v1/transactions/ingest", json=payload, headers=auth_headers
        )
        # Second request with same transaction_id
        response = await client.post(
            "/api/v1/transactions/ingest", json=payload, headers=auth_headers
        )
        assert response.status_code == 409

    async def test_ingest_unauthenticated(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/transactions/ingest", json=make_transaction_payload()
        )
        assert response.status_code == 401

    async def test_ingest_invalid_amount(
        self, client: AsyncClient, auth_headers: dict
    ):
        payload = make_transaction_payload({"amount": "-10.00"})
        response = await client.post(
            "/api/v1/transactions/ingest", json=payload, headers=auth_headers
        )
        assert response.status_code == 422

    async def test_ingest_invalid_transaction_type(
        self, client: AsyncClient, auth_headers: dict
    ):
        payload = make_transaction_payload({"transaction_type": "INVALID"})
        response = await client.post(
            "/api/v1/transactions/ingest", json=payload, headers=auth_headers
        )
        assert response.status_code == 422

    async def test_ingest_invalid_payment_method(
        self, client: AsyncClient, auth_headers: dict
    ):
        payload = make_transaction_payload({"payment_method": "BITCOIN"})
        response = await client.post(
            "/api/v1/transactions/ingest", json=payload, headers=auth_headers
        )
        assert response.status_code == 422

    async def test_ingest_high_amount_gets_flagged(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Transaction > $10,000 should have elevated fraud_score."""
        payload = make_transaction_payload({"amount": "15000.00"})
        response = await client.post(
            "/api/v1/transactions/ingest", json=payload, headers=auth_headers
        )
        assert response.status_code == 202
        assert response.json()["fraud_score"] >= 0.3

    async def test_ingest_pre_labelled_fraud(
        self, client: AsyncClient, auth_headers: dict
    ):
        """is_fraud=True should set fraud_score to 1.0 and status to flagged."""
        payload = make_transaction_payload({"is_fraud": True})
        response = await client.post(
            "/api/v1/transactions/ingest", json=payload, headers=auth_headers
        )
        assert response.status_code == 202
        data = response.json()
        assert data["fraud_score"] == 1.0
        assert data["status"] == "flagged"



# POST /batch


class TestBatch:

    async def test_batch_success(
        self, client: AsyncClient, auth_headers: dict
    ):
        transactions = [make_transaction_payload() for _ in range(5)]
        response = await client.post(
            "/api/v1/transactions/batch",
            json={"transactions": transactions},
            headers=auth_headers,
        )
        assert response.status_code == 202
        data = response.json()
        assert data["accepted"] == 5
        assert data["duplicates"] == 0

    async def test_batch_skips_duplicates(
        self, client: AsyncClient, auth_headers: dict
    ):
        payload = make_transaction_payload()
        # Insert once via ingest
        await client.post(
            "/api/v1/transactions/ingest", json=payload, headers=auth_headers
        )
        # Batch with the same transaction_id + 2 new ones
        batch = [payload, make_transaction_payload(), make_transaction_payload()]
        response = await client.post(
            "/api/v1/transactions/batch",
            json={"transactions": batch},
            headers=auth_headers,
        )
        assert response.status_code == 202
        data = response.json()
        assert data["accepted"] == 2
        assert data["duplicates"] == 1

    async def test_batch_too_large(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Pydantic max_length=1000 should reject oversized batches."""
        transactions = [make_transaction_payload() for _ in range(1001)]
        response = await client.post(
            "/api/v1/transactions/batch",
            json={"transactions": transactions},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_batch_empty(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Pydantic min_length=1 should reject empty batches."""
        response = await client.post(
            "/api/v1/transactions/batch",
            json={"transactions": []},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_batch_unauthenticated(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/transactions/batch",
            json={"transactions": [make_transaction_payload()]},
        )
        assert response.status_code == 401



# GET /


class TestListTransactions:

    async def test_list_returns_transactions(
        self,
        client: AsyncClient,
        auth_headers: dict,
        existing_transaction: Transaction,
    ):
        response = await client.get(
            "/api/v1/transactions/", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "transactions" in data
        assert "total" in data
        assert data["total"] >= 1

    async def test_list_filter_by_transaction_type(
        self, client: AsyncClient, auth_headers: dict
    ):
        # Insert a TRANSFER
        payload = make_transaction_payload({"transaction_type": "TRANSFER"})
        await client.post(
            "/api/v1/transactions/ingest", json=payload, headers=auth_headers
        )
        response = await client.get(
            "/api/v1/transactions/?transaction_type=TRANSFER",
            headers=auth_headers,
        )
        assert response.status_code == 200
        txns = response.json()["transactions"]
        assert all(t["transaction_type"] == "TRANSFER" for t in txns)

    async def test_list_filter_is_fraud(
        self, client: AsyncClient, auth_headers: dict
    ):
        payload = make_transaction_payload({"is_fraud": True})
        await client.post(
            "/api/v1/transactions/ingest", json=payload, headers=auth_headers
        )
        response = await client.get(
            "/api/v1/transactions/?is_fraud=true", headers=auth_headers
        )
        assert response.status_code == 200
        txns = response.json()["transactions"]
        assert all(t["is_fraud"] for t in txns)

    async def test_list_pagination(
        self, client: AsyncClient, auth_headers: dict
    ):
        # Insert 3 transactions
        for _ in range(3):
            await client.post(
                "/api/v1/transactions/ingest",
                json=make_transaction_payload(),
                headers=auth_headers,
            )
        # Request only 2
        response = await client.get(
            "/api/v1/transactions/?limit=2&offset=0", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["transactions"]) <= 2

    async def test_list_unauthenticated(self, client: AsyncClient):
        response = await client.get("/api/v1/transactions/")
        assert response.status_code == 401



# GET /{transaction_id}


class TestGetTransaction:

    async def test_get_existing_transaction(
        self,
        client: AsyncClient,
        auth_headers: dict,
        existing_transaction: Transaction,
    ):
        response = await client.get(
            f"/api/v1/transactions/{existing_transaction.transaction_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["transaction_id"] == existing_transaction.transaction_id

    async def test_get_nonexistent_returns_404(
        self, client: AsyncClient, auth_headers: dict
    ):
        response = await client.get(
            "/api/v1/transactions/txn_does_not_exist",
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_get_unauthenticated(
        self, client: AsyncClient, existing_transaction: Transaction
    ):
        response = await client.get(
            f"/api/v1/transactions/{existing_transaction.transaction_id}"
        )
        assert response.status_code == 401



# GET /stats/summary


class TestSummaryStats:

    async def test_stats_returns_correct_shape(
        self, client: AsyncClient, auth_headers: dict
    ):
        response = await client.get(
            "/api/v1/transactions/stats/summary", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        expected_keys = {
            "time_range_hours", "total_transactions", "total_amount",
            "transactions_by_type", "transactions_by_status",
            "fraud_count", "fraud_percentage", "average_fraud_score",
            "average_amount", "max_amount",
        }
        assert expected_keys.issubset(data.keys())

    async def test_stats_counts_fraud(
        self, client: AsyncClient, auth_headers: dict
    ):
        payload = make_transaction_payload({"is_fraud": True})
        await client.post(
            "/api/v1/transactions/ingest", json=payload, headers=auth_headers
        )
        response = await client.get(
            "/api/v1/transactions/stats/summary?hours=1", headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["fraud_count"] >= 1



# TransactionService unit tests (direct, no HTTP)


class TestTransactionService:

    async def test_create_transaction(self, db_session: AsyncSession):
        service = TransactionService(db_session)
        data = TransactionCreate(**make_transaction_payload())
        txn = await service.create_transaction(data)

        assert txn.id is not None
        assert txn.transaction_id == data.transaction_id
        assert txn.status in ("pending", "flagged")
        assert txn.fraud_score is not None
        assert txn.processing_time_ms is not None

    async def test_create_transaction_duplicate_raises(self, db_session: AsyncSession):
        from fastapi import HTTPException
        service = TransactionService(db_session)
        data = TransactionCreate(**make_transaction_payload())

        await service.create_transaction(data)
        with pytest.raises(HTTPException) as exc_info:
            await service.create_transaction(data)
        assert exc_info.value.status_code == 409

    async def test_get_transaction_not_found_raises(self, db_session: AsyncSession):
        from fastapi import HTTPException
        service = TransactionService(db_session)
        with pytest.raises(HTTPException) as exc_info:
            await service.get_transaction("txn_does_not_exist")
        assert exc_info.value.status_code == 404

    async def test_list_transactions_empty(self, db_session: AsyncSession):
        service = TransactionService(db_session)
        txns, total = await service.list_transactions()
        assert isinstance(txns, list)
        assert isinstance(total, int)

    async def test_create_batch_deduplication(self, db_session: AsyncSession):
        service = TransactionService(db_session)
        payload = make_transaction_payload()
        data = TransactionCreate(**payload)

        # First batch — all new
        result = await service.create_batch([data])
        assert result["accepted"] == 1
        assert result["duplicates"] == 0

        # Second batch — same transaction_id
        result = await service.create_batch([data])
        assert result["accepted"] == 0
        assert result["duplicates"] == 1



# Fraud scoring unit tests


class TestFraudScoring:

    async def test_pre_labelled_fraud_score_is_1(self, db_session: AsyncSession):
        service = TransactionService(db_session)
        data = TransactionCreate(**make_transaction_payload({"is_fraud": True}))
        txn = await service.create_transaction(data)
        assert txn.fraud_score == 1.0
        assert txn.status == "flagged"

    async def test_high_amount_increases_score(self, db_session: AsyncSession):
        service = TransactionService(db_session)
        normal = TransactionCreate(**make_transaction_payload({"amount": "100.00"}))
        large = TransactionCreate(**make_transaction_payload({"amount": "15000.00"}))

        txn_normal = await service.create_transaction(normal)
        txn_large = await service.create_transaction(large)

        assert txn_large.fraud_score > txn_normal.fraud_score

    async def test_international_transaction_increases_score(
        self, db_session: AsyncSession
    ):
        service = TransactionService(db_session)
        domestic = TransactionCreate(
            **make_transaction_payload({"country_code": "US"})
        )
        international = TransactionCreate(
            **make_transaction_payload({"country_code": "RU"})
        )
        txn_domestic = await service.create_transaction(domestic)
        txn_intl = await service.create_transaction(international)

        assert txn_intl.fraud_score > txn_domestic.fraud_score

    async def test_round_amount_increases_score(self, db_session: AsyncSession):
        service = TransactionService(db_session)
        normal = TransactionCreate(**make_transaction_payload({"amount": "137.53"}))
        round_amt = TransactionCreate(**make_transaction_payload({"amount": "500.00"}))

        txn_normal = await service.create_transaction(normal)
        txn_round = await service.create_transaction(round_amt)

        assert txn_round.fraud_score > txn_normal.fraud_score

    async def test_unusual_hour_increases_score(self, db_session: AsyncSession):
        service = TransactionService(db_session)

        # Normal hour (10 AM UTC)
        normal_time = datetime.now(timezone.utc).replace(hour=10)
        # Unusual hour (3 AM UTC)
        unusual_time = datetime.now(timezone.utc).replace(hour=3)

        normal = TransactionCreate(
            **make_transaction_payload({"transaction_time": normal_time.isoformat()})
        )
        unusual = TransactionCreate(
            **make_transaction_payload({"transaction_time": unusual_time.isoformat()})
        )
        txn_normal = await service.create_transaction(normal)
        txn_unusual = await service.create_transaction(unusual)

        assert txn_unusual.fraud_score > txn_normal.fraud_score

    async def test_score_does_not_exceed_1(self, db_session: AsyncSession):
        """Even with all rules triggered, score must be capped at 1.0."""
        service = TransactionService(db_session)
        # Trigger as many rules as possible
        worst_case = make_transaction_payload({
            "amount": "50000.00",           # high amount +0.3
            "country_code": "KP",           # international +0.2
            "is_fraud": False,
            "transaction_time": datetime.now(timezone.utc).replace(hour=3).isoformat(),
        })
        data = TransactionCreate(**worst_case)
        txn = await service.create_transaction(data)
        assert txn.fraud_score <= 1.0

    async def test_customer_velocity_increases_score(self, db_session: AsyncSession):
        """
        5+ transactions from the same customer in the last hour
        should increase the fraud score.
        """
        service = TransactionService(db_session)
        customer_id = str(uuid4())

        # Insert 5 transactions for the same customer
        for _ in range(5):
            data = TransactionCreate(
                **make_transaction_payload({"customer_id": customer_id})
            )
            await service.create_transaction(data)

        # 6th transaction — should have elevated score
        data = TransactionCreate(
            **make_transaction_payload({"customer_id": customer_id})
        )
        txn = await service.create_transaction(data)
        assert txn.fraud_score >= 0.3
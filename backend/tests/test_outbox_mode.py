"""Tests of variant B: outbox write and worker-side processing."""
import pytest
from sqlalchemy import select, func

from app.core.config import settings
from app.models.outbox import OutboxMessage
from app.models.transaction import Transaction
from app.services.transaction_service import TransactionService
from app.api.v1.schemas.transaction import TransactionCreate
from tests.conftest import make_transaction_payload


@pytest.fixture
def outbox_mode(monkeypatch):
    monkeypatch.setattr(settings, "INGEST_MODE", "outbox")


class TestOutboxIngest:
    async def test_ingest_returns_202_without_score(self, client, auth_headers, outbox_mode):
        response = await client.post(
            "/api/v1/transactions/ingest", json=make_transaction_payload(), headers=auth_headers
        )
        assert response.status_code == 202
        assert response.json()["fraud_score"] is None

    async def test_outbox_row_is_created_with_transaction(self, client, auth_headers, db_session, outbox_mode):
        payload = make_transaction_payload()
        await client.post("/api/v1/transactions/ingest", json=payload, headers=auth_headers)
        rows = (await db_session.execute(select(OutboxMessage))).scalars().all()
        assert len(rows) == 1
        assert rows[0].status == "pending"
        assert rows[0].event_type == "transaction.created"
        assert rows[0].payload["transaction_id"] == payload["transaction_id"]

    async def test_duplicate_creates_no_second_outbox_row(self, client, auth_headers, db_session, outbox_mode):
        payload = make_transaction_payload()
        first = await client.post("/api/v1/transactions/ingest", json=payload, headers=auth_headers)
        second = await client.post("/api/v1/transactions/ingest", json=payload, headers=auth_headers)
        assert first.status_code == 202
        assert second.status_code == 409
        count = await db_session.scalar(select(func.count()).select_from(OutboxMessage))
        assert count == 1


class TestWorkerSideProcessing:
    async def _ingest(self, db_session, overrides=None):
        service = TransactionService(db_session)
        data = TransactionCreate(**make_transaction_payload(overrides))
        return await service._create_transaction_outbox(data)

    async def test_processing_sets_score_status_and_time(self, db_session):
        txn = await self._ingest(db_session, {"amount": "15000.00"})
        assert txn.processed_at is None
        await TransactionService(db_session).process_existing_transaction(txn)
        assert txn.fraud_score >= 0.3
        assert txn.processed_at is not None
        assert txn.status in ("approved", "flagged")

    async def test_processing_twice_does_not_change_result(self, db_session):
        txn = await self._ingest(db_session)
        service = TransactionService(db_session)
        await service.process_existing_transaction(txn)
        first_time = txn.processed_at
        await service.process_existing_transaction(txn)
        assert txn.processed_at == first_time

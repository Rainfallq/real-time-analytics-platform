import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from uuid import UUID

from prometheus_client import start_http_server
from sqlalchemy import func, select, update

from app.core.config import settings
from app.core.metrics import (
    OUTBOX_PENDING,
    OUTBOX_PUBLISH_DURATION,
    OUTBOX_PUBLISH_FAILURES_TOTAL,
    OUTBOX_PUBLISHED_TOTAL,
)
from app.core.resilience import CircuitBreaker, CircuitOpenError, retry_async
from app.db.session import AsyncSessionLocal
from app.models.transaction import Transaction
from app.models.outbox import OutboxMessage

from kafka.config import KAFKA_TOPIC_RAW_DATA
from kafka.producer import KafkaProducer
from workers.common import install_stop_handler


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)

BATCH_SIZE = 50
POLL_INTERVAL_SECONDS = 2
STALE_PROCESSING_SECONDS = 60


class OutboxPublisher:
    """Publishes pending Outbox messages to a Kafka-compatible broker.

    Delivery to the broker is at-least-once. A crash after the broker accepted a
    message but before the row is marked as published gives a duplicate, which
    the worker removes (it skips transactions that are already processed).
    """

    def __init__(self) -> None:
        self.producer = KafkaProducer()
        self.breaker = CircuitBreaker(
            "kafka_broker",
            failure_threshold=settings.BREAKER_FAILURE_THRESHOLD,
            reset_timeout=settings.BREAKER_RESET_TIMEOUT_S,
        )
        self.stop = asyncio.Event()

    async def reserve_messages(self) -> list[dict]:
        """Reserve pending messages in PostgreSQL.

        FOR UPDATE SKIP LOCKED lets several publishers reserve different
        messages without blocking each other.
        """
        async with AsyncSessionLocal() as db:
            now = datetime.now(timezone.utc)
            stale_before = now - timedelta(seconds=STALE_PROCESSING_SECONDS)

            # Recover messages left in processing after a crash.
            await db.execute(
                update(OutboxMessage)
                .where(
                    OutboxMessage.status == "processing",
                    OutboxMessage.updated_at < stale_before,
                )
                .values(
                    status="pending",
                    retry_count=OutboxMessage.retry_count + 1,
                    last_error="Publisher reservation expired",
                )
            )

            result = await db.execute(
                select(OutboxMessage)
                .where(OutboxMessage.status == "pending")
                .order_by(OutboxMessage.created_at)
                .limit(BATCH_SIZE)
                .with_for_update(skip_locked=True)
            )
            messages = result.scalars().all()

            reserved = []
            for message in messages:
                message.status = "processing"
                reserved.append(
                    {
                        "id": message.id,
                        "aggregate_id": message.aggregate_id,
                        "event_type": message.event_type,
                        "payload": message.payload,
                    }
                )

            await db.commit()
            return reserved

    async def update_pending_gauge(self) -> None:
        async with AsyncSessionLocal() as db:
            pending = await db.scalar(
                select(func.count()).select_from(OutboxMessage).where(
                    OutboxMessage.status == "pending"
                )
            )
            OUTBOX_PENDING.set(pending or 0)

    async def mark_published(self, message_id: UUID) -> None:
        """Mark a message as published after broker acknowledgement (one statement)."""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                update(OutboxMessage)
                .where(OutboxMessage.id == message_id)
                .values(
                    status="published",
                    published_at=datetime.now(timezone.utc),
                    last_error=None,
                )
            )
            if result.rowcount == 0:
                raise RuntimeError(f"Outbox message not found: {message_id}")
            await db.commit()

    async def mark_failed(self, message_id: UUID, error: Exception) -> None:
        """Return a failed message to pending for another attempt."""
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(OutboxMessage)
                .where(OutboxMessage.id == message_id)
                .values(
                    status="pending",
                    retry_count=OutboxMessage.retry_count + 1,
                    last_error=str(error)[:1000],
                )
            )
            await db.commit()

    async def publish_message(self, message: dict) -> None:
        """Publish one reserved Outbox message with retry and circuit breaker."""
        message_id = message["id"]
        started = time.perf_counter()

        event = {
            **message["payload"],
            "event_type": message["event_type"],
            "outbox_id": str(message_id),
        }

        try:
            await retry_async(
                lambda: self.breaker.call(
                    self.producer.send,
                    topic=KAFKA_TOPIC_RAW_DATA,
                    key=str(message["aggregate_id"]),
                    message=event,
                ),
                attempts=settings.PUBLISH_MAX_ATTEMPTS,
                base_delay=settings.RETRY_BASE_DELAY_S,
                max_delay=settings.RETRY_MAX_DELAY_S,
            )

            # Only mark published after broker acknowledgement.
            await self.mark_published(message_id)
            OUTBOX_PUBLISHED_TOTAL.inc()
            OUTBOX_PUBLISH_DURATION.observe(time.perf_counter() - started)

        except Exception as exc:
            OUTBOX_PUBLISH_FAILURES_TOTAL.inc()
            logger.error("Failed to publish Outbox message %s: %s", message_id, exc)
            try:
                await self.mark_failed(message_id, exc)
            except Exception:
                logger.exception("Failed to update Outbox status: id=%s", message_id)
            raise

    async def run(self) -> None:
        """Poll PostgreSQL and publish pending messages until stopped."""
        install_stop_handler(self.stop)
        start_http_server(settings.PUBLISHER_METRICS_PORT)
        await self.producer.start()
        logger.info("Outbox Publisher started. Topic: %s", KAFKA_TOPIC_RAW_DATA)

        try:
            while not self.stop.is_set():
                try:
                    await self.update_pending_gauge()

                    # While the broker is unavailable, do not reserve messages:
                    # they stay pending and the backlog alert shows the problem.
                    if not self.breaker.allow():
                        await asyncio.sleep(1)
                        continue

                    messages = await self.reserve_messages()

                    if not messages:
                        await asyncio.sleep(POLL_INTERVAL_SECONDS)
                        continue

                    for message in messages:
                        if self.stop.is_set():
                            # Give the rest back so another publisher can take it.
                            await self.mark_failed(message["id"], RuntimeError("publisher stopping"))
                            continue
                        try:
                            await self.publish_message(message)
                        except CircuitOpenError:
                            continue
                        except Exception:
                            continue

                except Exception:
                    logger.exception("Outbox Publisher iteration failed")
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
        finally:
            await self.producer.stop()
            logger.info("Outbox Publisher stopped")


async def main() -> None:
    await OutboxPublisher().run()


if __name__ == "__main__":
    asyncio.run(main())

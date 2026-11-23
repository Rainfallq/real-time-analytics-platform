
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update

from app.db.session import AsyncSessionLocal
from app.models.transaction import Transaction
from app.models.outbox import OutboxMessage

from kafka.config import KAFKA_TOPIC_RAW_DATA
from kafka.producer import KafkaProducer


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)

BATCH_SIZE = 50
POLL_INTERVAL_SECONDS = 2
STALE_PROCESSING_SECONDS = 60


class OutboxPublisher:
    """
    Publishes pending Outbox messages to a Kafka-compatible broker.
    """

    def __init__(self) -> None:
        self.producer = KafkaProducer()

    async def reserve_messages(self) -> list[dict]:
        """
        Reserve pending messages in PostgreSQL.

        FOR UPDATE SKIP LOCKED allows multiple publishers
        to reserve different messages without blocking each other.
        """

        async with AsyncSessionLocal() as db:
            now = datetime.now(timezone.utc)
            stale_before = now - timedelta(
                seconds=STALE_PROCESSING_SECONDS
            )

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

            # Lock and select a batch of pending messages.
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

            # Release PostgreSQL locks after reservation.
            await db.commit()

            return reserved

    async def mark_published(self, message_id: UUID) -> None:
        """Mark a message as published after broker acknowledgement."""

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(OutboxMessage).where(
                    OutboxMessage.id == message_id
                )
            )

            message = result.scalar_one_or_none()

            if message is None:
                raise RuntimeError(
                    f"Outbox message not found: {message_id}"
                )

            message.status = "published"
            message.published_at = datetime.now(timezone.utc)
            message.last_error = None

            await db.commit()

    async def mark_failed(
        self,
        message_id: UUID,
        error: Exception,
    ) -> None:
        """Return a failed message to pending for another attempt."""

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(OutboxMessage).where(
                    OutboxMessage.id == message_id
                )
            )

            message = result.scalar_one_or_none()

            if message is None:
                logger.error(
                    "Cannot update missing Outbox message: %s",
                    message_id,
                )
                return

            message.status = "pending"
            message.retry_count += 1
            message.last_error = str(error)[:1000]

            await db.commit()

    async def publish_message(self, message: dict) -> None:
        """Publish one reserved Outbox message."""

        message_id = message["id"]

        event = {
            **message["payload"],
            "event_type": message["event_type"],
            "outbox_id": str(message_id),
        }

        try:
            await self.producer.send(
                topic=KAFKA_TOPIC_RAW_DATA,
                key=str(message["aggregate_id"]),
                message=event,
            )

            # Only mark published after broker acknowledgement.
            await self.mark_published(message_id)

            logger.info(
                "Outbox message published: id=%s aggregate_id=%s",
                message_id,
                message["aggregate_id"],
            )

        except Exception as exc:
            logger.exception(
                "Failed to publish Outbox message: id=%s",
                message_id,
            )

            try:
                await self.mark_failed(message_id, exc)
            except Exception:
                logger.exception(
                    "Failed to update Outbox status: id=%s",
                    message_id,
                )

            raise

    async def run(self) -> None:
        """Continuously poll PostgreSQL and publish pending messages."""

        await self.producer.start()

        logger.info(
            "Outbox Publisher started. Topic: %s",
            KAFKA_TOPIC_RAW_DATA,
        )

        try:
            while True:
                try:
                    messages = await self.reserve_messages()

                    if not messages:
                        await asyncio.sleep(POLL_INTERVAL_SECONDS)
                        continue

                    logger.info(
                        "Reserved %d Outbox messages",
                        len(messages),
                    )

                    for message in messages:
                        try:
                            await self.publish_message(message)
                        except Exception:
                            # Continue with the remaining messages.
                            continue

                except Exception:
                    logger.exception(
                        "Outbox Publisher iteration failed"
                    )
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)

        finally:
            await self.producer.stop()
            logger.info("Outbox Publisher stopped")


async def main() -> None:
    publisher = OutboxPublisher()
    await publisher.run()


if __name__ == "__main__":
    asyncio.run(main())

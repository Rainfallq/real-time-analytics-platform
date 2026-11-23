
import asyncio
import logging
from uuid import UUID

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.transaction import Transaction
from app.services.transaction_service import TransactionService

from kafka.consumer import KafkaConsumer
from kafka.config import KAFKA_TOPIC_RAW_DATA


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)

CONSUMER_GROUP_ID = "transaction-workers"


async def process_message(message: dict) -> None:
    """
    Load a transaction from PostgreSQL and process it.
    """

    event_type = message.get("event_type")

    if event_type != "transaction.created":
        logger.warning(
            "Unknown event type: %s. Skipping message.",
            event_type,
        )
        return

    transaction_db_id = message.get("transaction_db_id")

    if not transaction_db_id:
        raise ValueError("Message does not contain transaction_db_id")

    try:
        transaction_id = UUID(str(transaction_db_id))
    except ValueError as exc:
        raise ValueError(
            f"Invalid transaction_db_id: {transaction_db_id}"
        ) from exc

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Transaction)
            .where(Transaction.id == transaction_id)
            .with_for_update()
        )

        transaction = result.scalar_one_or_none()

        if transaction is None:
            raise ValueError(
                f"Transaction not found: {transaction_id}"
            )

        service = TransactionService(db)

        await service.process_existing_transaction(transaction)


async def run_worker() -> None:
    consumer = KafkaConsumer(
        topic=KAFKA_TOPIC_RAW_DATA,
        group_id=CONSUMER_GROUP_ID,
    )

    await consumer.start()

    logger.info(
        "Transaction Worker started. Topic: %s",
        KAFKA_TOPIC_RAW_DATA,
    )

    try:
        while True:
            try:
                record = await consumer.get_message(timeout_ms=1000)

            except asyncio.TimeoutError:
                continue

            try:
                if not isinstance(record.value, dict):
                    raise ValueError(
                        "Kafka message value must be a JSON object"
                    )

                logger.info(
                    "Message received: topic=%s partition=%s offset=%s",
                    record.topic,
                    record.partition,
                    record.offset,
                )

                await process_message(record.value)

                # Commit Kafka offset only after successful processing
                await consumer.commit()

                logger.info(
                    "Message successfully handled: offset=%s",
                    record.offset,
                )

            except Exception:
                logger.exception(
                    "Message processing failed. "
                    "Offset will not be committed."
                )
                raise

    finally:
        await consumer.stop()
        logger.info("Transaction Worker stopped")


if __name__ == "__main__":
    asyncio.run(run_worker())

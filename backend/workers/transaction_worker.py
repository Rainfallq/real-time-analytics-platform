import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from uuid import UUID

from prometheus_client import start_http_server
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError

from app.core.config import settings
from app.core.metrics import (
    CONSUMER_LAG_MESSAGES,
    DLQ_MESSAGES_TOTAL,
    PIPELINE_LAG_SECONDS,
    WORKER_FAILURES_TOTAL,
    WORKER_PROCESSED_TOTAL,
)
from app.core.resilience import CircuitBreaker, retry_async
from app.db.session import AsyncSessionLocal
from app.models.transaction import Transaction
from app.services.transaction_service import TransactionService

from kafka.config import KAFKA_TOPIC_RAW_DATA
from kafka.consumer import KafkaConsumer
from kafka.producer import KafkaProducer
from workers.common import install_stop_handler


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)

CONSUMER_GROUP_ID = "transaction-workers"
PROCESSED = "processed"
DEAD_LETTERED = "dead_lettered"


def is_transient(exc: BaseException) -> bool:
    """Errors caused by the infrastructure (database, network).

    They are retried without limit, because the message itself is fine and will
    be processed as soon as the dependency is back. Giving up on them would
    move good messages to the dead-letter topic during a short outage.
    """
    if isinstance(exc, (OperationalError, InterfaceError, ConnectionError, OSError, asyncio.TimeoutError)):
        return True
    if isinstance(exc, DBAPIError) and exc.connection_invalidated:
        return True
    return False


def _delay(failures: int, base: float, cap: float) -> float:
    return min(cap, base * (2 ** (failures - 1)))


async def handle_record(
    value: Any,
    *,
    process: Callable[[Any], Awaitable[None]],
    send_dlq: Callable[[Any, BaseException], Awaitable[None]],
    max_attempts: int = 3,
    base_delay: float = 0.2,
    max_delay: float = 5.0,
    transient: Callable[[BaseException], bool] = is_transient,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    should_stop: Callable[[], bool] = lambda: False,
) -> str:
    """Process one message and decide what happens to it.

    - success: PROCESSED
    - malformed message (ValueError): sent to the dead-letter topic at once
    - transient error: retried with backoff until it works
    - other error: retried max_attempts times, then sent to the dead-letter topic
    The caller commits the Kafka offset after this function returns.
    """
    permanent_failures = 0
    transient_failures = 0
    while True:
        try:
            await process(value)
            return PROCESSED
        except ValueError as exc:
            WORKER_FAILURES_TOTAL.inc()
            await send_dlq(value, exc)
            return DEAD_LETTERED
        except Exception as exc:
            WORKER_FAILURES_TOTAL.inc()
            if transient(exc):
                transient_failures += 1
                if should_stop():
                    raise
                logger.warning("Transient error, will retry: %s", exc)
                await sleep(_delay(transient_failures, base_delay, max_delay))
                continue
            permanent_failures += 1
            if permanent_failures >= max_attempts:
                await send_dlq(value, exc)
                return DEAD_LETTERED
            await sleep(_delay(permanent_failures, base_delay, max_delay))


async def process_message(message: dict) -> None:
    """Load a transaction from PostgreSQL and process it."""

    event_type = message.get("event_type")

    if event_type != "transaction.created":
        logger.warning("Unknown event type: %s. Skipping message.", event_type)
        return

    transaction_db_id = message.get("transaction_db_id")

    if not transaction_db_id:
        raise ValueError("Message does not contain transaction_db_id")

    try:
        transaction_id = UUID(str(transaction_db_id))
    except ValueError as exc:
        raise ValueError(f"Invalid transaction_db_id: {transaction_db_id}") from exc

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Transaction).where(Transaction.id == transaction_id).with_for_update()
        )

        transaction = result.scalar_one_or_none()

        if transaction is None:
            raise ValueError(f"Transaction not found: {transaction_id}")

        already_processed = transaction.processed_at is not None

        service = TransactionService(db)
        await service.process_existing_transaction(transaction)

        if not already_processed and transaction.processed_at and transaction.ingested_at:
            PIPELINE_LAG_SECONDS.observe(
                (transaction.processed_at - transaction.ingested_at).total_seconds()
            )


async def run_worker() -> None:
    stop = asyncio.Event()
    install_stop_handler(stop)
    start_http_server(settings.WORKER_METRICS_PORT)

    consumer = KafkaConsumer(topic=KAFKA_TOPIC_RAW_DATA, group_id=CONSUMER_GROUP_ID)
    dlq_producer = KafkaProducer()
    dlq_breaker = CircuitBreaker(
        "dlq_broker",
        failure_threshold=settings.BREAKER_FAILURE_THRESHOLD,
        reset_timeout=settings.BREAKER_RESET_TIMEOUT_S,
    )

    async def send_dlq(value: Any, exc: BaseException) -> None:
        payload = {
            "original": value,
            "error": f"{type(exc).__name__}: {exc}"[:500],
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        await retry_async(
            lambda: dlq_breaker.call(
                dlq_producer.send,
                topic=settings.KAFKA_TOPIC_DLQ,
                key=str(value.get("transaction_db_id")) if isinstance(value, dict) else None,
                message=payload,
            ),
            attempts=settings.PUBLISH_MAX_ATTEMPTS,
            base_delay=settings.RETRY_BASE_DELAY_S,
            max_delay=settings.RETRY_MAX_DELAY_S,
        )
        DLQ_MESSAGES_TOTAL.inc()
        logger.error("Message moved to dead-letter topic: %s", payload["error"])

    await consumer.start()
    await dlq_producer.start()
    logger.info("Transaction Worker started. Topic: %s", KAFKA_TOPIC_RAW_DATA)

    last_lag_update = 0.0
    try:
        while not stop.is_set():
            try:
                record = await consumer.get_message(timeout_ms=1000)
            except asyncio.TimeoutError:
                record = None

            now = time.monotonic()
            if now - last_lag_update > 5:
                try:
                    CONSUMER_LAG_MESSAGES.set(await consumer.lag())
                except Exception:
                    logger.debug("Could not read consumer lag", exc_info=True)
                last_lag_update = now

            if record is None:
                continue

            logger.info(
                "Message received: partition=%s offset=%s", record.partition, record.offset
            )

            # Keep the same record until it is either processed or dead-lettered.
            while True:
                try:
                    if not isinstance(record.value, dict):
                        raise ValueError("Kafka message value must be a JSON object")
                    outcome = await handle_record(
                        record.value,
                        process=process_message,
                        send_dlq=send_dlq,
                        max_attempts=settings.WORKER_MAX_ATTEMPTS,
                        base_delay=settings.RETRY_BASE_DELAY_S,
                        max_delay=settings.RETRY_MAX_DELAY_S,
                        should_stop=stop.is_set,
                    )
                    break
                except Exception:
                    # Only reached when the dead-letter topic is not available
                    # or the worker is stopping. Do not commit, try again.
                    logger.exception("Could not finish message, offset not committed")
                    if stop.is_set():
                        outcome = None
                        break
                    await asyncio.sleep(settings.RETRY_MAX_DELAY_S)

            if outcome is None:
                break

            if outcome == PROCESSED:
                WORKER_PROCESSED_TOTAL.inc()
            # Commit the offset only after the message is processed or dead-lettered
            await consumer.commit()
    finally:
        await consumer.stop()
        await dlq_producer.stop()
        logger.info("Transaction Worker stopped")


if __name__ == "__main__":
    asyncio.run(run_worker())


import json
import logging
from typing import Any

from aiokafka import AIOKafkaProducer

from kafka.config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_CLIENT_ID,
)

logger = logging.getLogger(__name__)


class KafkaProducer:
    """
    Asynchronous Kafka-compatible producer.

    Sends JSON messages to Redpanda or another Kafka-compatible broker.
    """

    def __init__(self) -> None:
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        """Create a connection to the Kafka broker."""
        if self._producer is not None:
            return

        self._producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            client_id=KAFKA_CLIENT_ID,
            acks="all",
            enable_idempotence=True,
        )

        try:
            await self._producer.start()
            logger.info(
                "Kafka producer connected to %s",
                KAFKA_BOOTSTRAP_SERVERS,
            )
        except Exception:
            self._producer = None
            logger.exception("Failed to start Kafka producer")
            raise

    async def send(
        self,
        topic: str,
        message: dict[str, Any],
        key: str | None = None,
    ) -> None:
        """
        Serialize a Python dictionary to JSON and send it.

        Waits for broker acknowledgement before returning.
        """
        if self._producer is None:
            raise RuntimeError(
                "Kafka producer is not started. Call start() first."
            )

        value = json.dumps(
            message,
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")

        key_bytes = key.encode("utf-8") if key is not None else None

        try:
            metadata = await self._producer.send_and_wait(
                topic,
                value=value,
                key=key_bytes,
            )

            logger.info(
                "Message published: topic=%s partition=%s offset=%s",
                metadata.topic,
                metadata.partition,
                metadata.offset,
            )

        except Exception:
            logger.exception(
                "Failed to publish message to topic %s",
                topic,
            )
            raise

    async def stop(self) -> None:
        """Close the producer connection."""
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None
            logger.info("Kafka producer stopped")

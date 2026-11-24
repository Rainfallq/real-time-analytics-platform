import json
import logging
from typing import Any
import asyncio
from aiokafka import AIOKafkaConsumer
from aiokafka.structs import ConsumerRecord

from kafka.config import KAFKA_BOOTSTRAP_SERVERS

logger = logging.getLogger(__name__)


class KafkaConsumer:
    """
    Asynchronous Kafka-compatible consumer.

    Reads JSON messages and supports manual offset commits.
    """

    def __init__(self, topic: str, group_id: str) -> None:
        self.topic = topic
        self.group_id = group_id
        self._consumer: AIOKafkaConsumer | None = None

    async def start(self) -> None:
        """Connect to the broker and subscribe to the topic."""
        if self._consumer is not None:
            return

        self._consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id=self.group_id,
            client_id=f"{self.group_id}-consumer",
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            value_deserializer=lambda value: json.loads(
                value.decode("utf-8")
            ),
            key_deserializer=lambda key: (
                key.decode("utf-8") if key is not None else None
            ),
        )

        try:
            await self._consumer.start()
            logger.info(
                "Kafka consumer started: topic=%s group=%s",
                self.topic,
                self.group_id,
            )
        except Exception:
            self._consumer = None
            logger.exception("Failed to start Kafka consumer")
            raise

    async def get_message(self, timeout_ms: int = 10000) -> ConsumerRecord:
        """Read one message from the topic with a timeout."""
        if self._consumer is None:
            raise RuntimeError(
                "Kafka consumer is not started. Call start() first."
            )

        return await asyncio.wait_for(
            self._consumer.getone(),
            timeout=timeout_ms / 1000,
        )

    async def commit(self) -> None:
        """Commit consumed offsets manually."""
        if self._consumer is None:
            raise RuntimeError(
                "Kafka consumer is not started. Call start() first."
            )

        await self._consumer.commit()

    async def lag(self) -> int:
        """Number of messages in the assigned partitions not yet read."""
        if self._consumer is None:
            return 0
        total = 0
        for tp in self._consumer.assignment():
            high = self._consumer.highwater(tp)
            if high is None:
                continue
            position = await self._consumer.position(tp)
            total += max(0, high - position)
        return total

    async def stop(self) -> None:
        """Close the consumer connection."""
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None
            logger.info("Kafka consumer stopped")

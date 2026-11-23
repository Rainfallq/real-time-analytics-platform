import uuid

from sqlalchemy import (
    Column,
    Uuid,
    String,
    Integer,
    DateTime,
    ForeignKey,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db.base import Base, TimestampMixin


class OutboxMessage(Base, TimestampMixin):
    """
    Outbox message for reliable asynchronous transaction processing.
    """

    __tablename__ = "outbox_messages"

    id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique outbox message id",
    )

    aggregate_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("transactions.id"),
        nullable=False,
        comment="ID of the related transaction",
    )

    event_type = Column(
        String(100),
        nullable=False,
        comment="Event type, e.g. transaction.created",
    )

    payload = Column(
        JSONB,
        nullable=False,
        comment="Event payload for asynchronous processing",
    )

    status = Column(
        String(20),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        comment="pending or published",
    )

    retry_count = Column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Number of publishing attempts",
    )

    last_error = Column(
        String(1000),
        nullable=True,
        comment="Last publishing error",
    )

    published_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when message was published to Kafka",
    )

    __table_args__ = (
        Index("ix_outbox_status_created", "status", "created_at"),
        Index("ix_outbox_aggregate_id", "aggregate_id"),
    )

    def __repr__(self):
        return (
            f"<OutboxMessage id={self.id} "
            f"event_type={self.event_type!r} status={self.status!r}>"
        )

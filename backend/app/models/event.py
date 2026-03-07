from sqlalchemy import Column, String, Boolean, Float, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from datetime import datetime
from sqlalchemy.sql import func


from app.db.base import TimestampMixin, Base


class Event(Base, TimestampMixin):
    """Event model for analytics data"""

    __tablename__ = "events"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="Event id"
    )

    event_type = Column(
        String(255),
        nullable=False,
        index=True,
        comment="Event type (e.g., user.login, api.request)"
    )

    source_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Data Source id"
    )

    event_time = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
        comment="Event actual occur time"
    )

    ingested_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When event was ingested into the system"
    )

    payload = Column(
        JSONB,
        nullable=False,
        comment="Event data(flexible json)"
    )

    event_metadata = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Additional metadata"
    )

    severity = Column(
        Float,
        nullable=False,
        default=0.5,
        comment="Severity range 0.0-1.0"
    )

    anomaly_score = Column(
        Float,
        nullable=True,
        comment="Anomaly score 0.0-1.0"
    )   

    __table_args__= (
        Index('ix-events-type-time', 'event_type', 'event_time'),
        Index('ix-events-source-time', 'source_id', 'event_time'),
        Index('ix-events-severity', 'severity', postgresql_where=(Column('severity') > 0.7)),
        # JSONB index using gin for fast queries on payload
        Index('ix-events-payload-gin', 'payload', postgresql_using='gin') 
    )

    def __repr__(self):
        return f"Event: {self.event_type} at {self.event_time}"


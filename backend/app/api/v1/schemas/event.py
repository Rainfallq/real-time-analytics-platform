from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Dict, List, Any




class EventCreate(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=255)
    source_id: UUID = Field(..., description="Source identifier")
    event_time: datetime | None = Field(default=None, description="When event occured")
    payload: Dict[str, Any] = Field(..., description="Event data")
    event_metadata: Dict[str, Any] | None = Field(default={}, description="Additional data")
    severity: float | None = Field(default=0.5, ge=0.0, le=1.0, description="Event Severity range 0.0-1.0")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_type": "face_detected",
                "source_id": "123e4567-e89b-12d3-a456-426614174000",
                "payload": {
                    "confidence": 0.95,
                    "person_id": "person_123",
                    "bbox": {"x": 100, "y": 150, "width": 80, "height": 100}
                },
                "event_metadata": {
                    "camera_name": "Entrance Camera 1",
                    "location": "main_entrance"
                },
                "severity": 0.3
            }
        }
    )


class EventBatchCreate(BaseModel):
    events: List[EventCreate] = Field(..., min_length=1, max_length=1000)


class EventResponse(BaseModel):
    id: UUID
    event_type: str
    source_id: UUID
    event_time: datetime
    ingested_at: datetime
    payload: Dict[str, Any]
    event_metadata: Dict[str, Any]
    severity: float
    anomaly_score: float | None = None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes = True
    )


class EventListResponse(BaseModel):
    """Paginated event list response"""
    events: List[EventResponse]
    total: int
    limit: int
    offset: int


class EventQuery(BaseModel):
    event_type: str | None = None
    source_id: UUID | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    min_severity: float | None = Field(default=None, ge=0.0, le=1.0)
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)

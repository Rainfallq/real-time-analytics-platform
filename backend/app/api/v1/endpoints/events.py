from fastapi import APIRouter, status, Depends, BackgroundTasks, HTTPException
from app.api.v1.schemas.event import (
    EventCreate,
    EventBatchCreate,
    EventResponse,
    EventListResponse, 
    EventQuery
)
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, get_current_active_user
from app.models.user import User
from app.models.event import Event
from app.core.config import settings
from datetime import datetime, timezone, timedelta
from uuid import UUID
from sqlalchemy import select, func, and_


router = APIRouter()


@router.post('/ingest', response_model=EventResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_event(
    event_data: EventCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    new_event = Event(
        event_type=event_data.event_type,
        source_id=event_data.source_id,
        event_time=event_data.event_time or datetime.now(timezone.utc),
        payload=event_data.payload, 
        event_metadata=event_data.event_metadata or {},
        severity=event_data.severity or 0.5
    )

    db.add(new_event)
    await db.commit()
    await db.refresh(new_event)
    
    # todo: Send to Kafka in background (Phase 2)
    # background_tasks.add_task(send_to_kafka, new_event)
    
    return new_event


@router.post('/batch', status_code=status.HTTP_202_ACCEPTED)
async def ingest_batch(
    batch_data: EventBatchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if len(batch_data.events) > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 1000 events per batch"
        )

    events = []
    for event_data in batch_data.events:
        event = Event(
            event_type=event_data.event_type,
            source_id=event_data.source_id,
            event_time=event_data.event_time or datetime.now(timezone.utc),
            payload=event_data.payload, 
            event_metadata=event_data.event_metadata or {},
            severity=event_data.severity or 0.5
        )
        events.append(event)

    db.add_all(events)
    await db.commit()

    return {
        "accepted": len(events),
        "status": "processing"
    }


@router.get("/", response_model=EventListResponse)
async def list_events(
    event_type: str | None = None,
    source_id: UUID | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    min_severity: float | None = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = select(Event)
    
    filters = []
    if event_type:
        filters.append(Event.event_type == event_type)
    if source_id:
        filters.append(Event.source_id == source_id)
    if start_time:
        filters.append(Event.event_time >= start_time)
    if end_time: 
        filters.append(Event.event_time <= end_time)
    if min_severity is not None:
        filters.append(Event.severity >= min_severity)

    if filters:
        query = query.where(and_(*filters))

    query = query.order_by(Event.event_time.desc())
    query = query.limit(min(limit, 1000)).offset(offset)

    result = await db.execute(query)
    events = result.scalars().all()

    count_query = select(func.count()).select_from(Event)
    if filters:
        count_query = count_query.where(and_(*filters))

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    return {
        "events": events,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get single event by ID"""
    try:
        event_uuid = UUID(event_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid event ID"
        )
    
    result = await db.execute(
        select(Event).where(Event.id == event_uuid)
    )
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    return event


@router.get("/stats/summary")
async def get_summary_stats(
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user)
):
    """
    Get summary statistics for last N hours
    """
    start_time = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Total events
    total_result = await db.execute(
        select(func.count())
        .select_from(Event)
        .where(Event.event_time >= start_time)
    )
    total_events = total_result.scalar()

    # Event by type
    type_result = await db.execute(
        select(Event.event_type, func.count())
        .where(Event.event_time >= start_time)
        .group_by(Event.event_type)
    )
    events_by_type = {row[0]: row[1] for row in type_result}

    # Average severity
    avg_result = await db.execute(
        select(func.avg(Event.severity))
        .where(Event.event_time >= start_time)
    )
    avg_severity = avg_result.scalar() or 0.0

    return {
        "time_range_hours": hours,
        "total_events": total_events,
        "events_per_hour": round(total_events/hours, 2) if hours > 0 else 0,
        "events_by_type": events_by_type,
        "average_severity": round(avg_severity, 2)
    }



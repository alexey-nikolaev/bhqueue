"""
Queue API endpoints.

Handles:
- User queue submissions (join, position, checkpoint, result)
- Queue updates from Reddit (Devvit) and Telegram
- Queue status aggregation
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user, get_current_user_optional
from app.database import get_db
from app.models import Club, ParsedUpdate, User, QueueSession, PositionUpdate, Event, Queue, SpatialMarker
from app.models.queue_session import QueueResult
from app.services.event_service import get_current_klubnacht
from app.services.queue_parser import (
    parse_queue_message,
    estimate_wait_from_spatial_marker,
    estimate_wait_from_queue_length,
)

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

# --- External Source Updates ---

class RawUpdateRequest(BaseModel):
    """
    Raw update from external sources (Reddit, Telegram).
    """
    source: str  # 'reddit', 'telegram'
    source_id: str  # Original message/comment ID
    content: str  # Raw message text
    parent_content: Optional[str] = None  # Parent message for context
    author_name: Optional[str] = None
    source_timestamp: Optional[str] = None  # ISO format


class UpdateResponse(BaseModel):
    """Response for queue update submission."""
    success: bool
    message: str
    update_id: Optional[str] = None
    parsed_wait_minutes: Optional[int] = None
    parsed_queue_length: Optional[str] = None
    parsed_spatial_marker: Optional[str] = None


# --- User Queue Session ---

class JoinQueueRequest(BaseModel):
    """Request to join a queue."""
    club_slug: str = "berghain"
    queue_type: str = "main"  # main, guestlist, reentry
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class PositionUpdateRequest(BaseModel):
    """GPS position update from user."""
    latitude: float
    longitude: float
    accuracy_meters: Optional[float] = None
    recorded_at: Optional[str] = None  # ISO format, defaults to now


class CheckpointRequest(BaseModel):
    """User confirms passing a spatial marker."""
    marker_id: uuid.UUID


class ResultRequest(BaseModel):
    """User reports queue result."""
    result: str  # 'admitted', 'rejected'


class QueueSessionResponse(BaseModel):
    """User's queue session info."""
    id: uuid.UUID
    queue_type: str
    joined_at: str
    result: Optional[str] = None
    result_at: Optional[str] = None
    wait_duration_minutes: Optional[int] = None
    position_count: int = 0
    last_marker: Optional[str] = None

    class Config:
        from_attributes = True


# --- Queue Status ---

class QueueStatusResponse(BaseModel):
    """Current queue status aggregated from all sources."""
    estimated_wait_minutes: Optional[int] = None
    confidence: str  # 'low', 'medium', 'high'
    data_points: int
    last_update: Optional[str] = None
    spatial_marker: Optional[str] = None
    queue_length: Optional[str] = None
    sources: dict  # Count by source


# =============================================================================
# User Queue Session Endpoints
# =============================================================================

@router.post("/join", response_model=QueueSessionResponse)
async def join_queue(
    request: JoinQueueRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Start a new queue session.
    
    Call this when user joins the queue. Optionally provide initial GPS position.
    """
    # Get club
    result = await db.execute(
        select(Club).where(Club.slug == request.club_slug)
    )
    club = result.scalar_one_or_none()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    
    # Check for existing active session
    result = await db.execute(
        select(QueueSession)
        .where(
            QueueSession.user_id == current_user.id,
            QueueSession.result == None,
        )
        .order_by(QueueSession.joined_at.desc())
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail="You already have an active queue session. Leave or report result first.",
        )
    
    # Get or create current event
    current_event = get_current_klubnacht()
    
    # For now, create a placeholder event if none exists
    # In production, this should be handled better
    result = await db.execute(
        select(Event)
        .where(Event.club_id == club.id)
        .order_by(Event.start_time.desc())
        .limit(1)
    )
    event = result.scalar_one_or_none()
    
    if not event:
        # Create a temporary event
        from app.models import Event
        event = Event(
            id=uuid.uuid4(),
            club_id=club.id,
            name="Klubnacht",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(hours=24),
        )
        db.add(event)
        await db.flush()
    
    # Create queue session
    now = datetime.utcnow()
    session = QueueSession(
        id=uuid.uuid4(),
        user_id=current_user.id,
        event_id=event.id,
        queue_type=request.queue_type,
        joined_at=now,
    )
    db.add(session)
    await db.flush()
    
    # Add initial position if provided
    if request.latitude and request.longitude:
        position = PositionUpdate(
            id=uuid.uuid4(),
            session_id=session.id,
            latitude=request.latitude,
            longitude=request.longitude,
            recorded_at=now,
        )
        db.add(position)
    
    await db.commit()
    await db.refresh(session)
    
    return QueueSessionResponse(
        id=session.id,
        queue_type=session.queue_type,
        joined_at=session.joined_at.isoformat(),
        position_count=1 if request.latitude else 0,
    )


@router.get("/session", response_model=Optional[QueueSessionResponse])
async def get_current_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get user's current active queue session.
    
    Returns null if user is not in a queue.
    """
    result = await db.execute(
        select(QueueSession)
        .options(selectinload(QueueSession.position_updates))
        .where(
            QueueSession.user_id == current_user.id,
            QueueSession.result == None,
        )
        .order_by(QueueSession.joined_at.desc())
    )
    session = result.scalar_one_or_none()
    
    if not session:
        return None
    
    return QueueSessionResponse(
        id=session.id,
        queue_type=session.queue_type,
        joined_at=session.joined_at.isoformat(),
        result=session.result,
        result_at=session.result_at.isoformat() if session.result_at else None,
        wait_duration_minutes=session.wait_duration_minutes,
        position_count=len(session.position_updates) if session.position_updates else 0,
    )


@router.post("/position", response_model=dict)
async def submit_position(
    request: PositionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a GPS position update.
    
    Call periodically while user is in the queue to track movement.
    """
    # Get active session
    result = await db.execute(
        select(QueueSession)
        .where(
            QueueSession.user_id == current_user.id,
            QueueSession.result == None,
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=400,
            detail="No active queue session. Join the queue first.",
        )
    
    # Parse recorded_at
    if request.recorded_at:
        try:
            recorded_at = datetime.fromisoformat(request.recorded_at.replace('Z', '+00:00'))
        except ValueError:
            recorded_at = datetime.utcnow()
    else:
        recorded_at = datetime.utcnow()
    
    # Create position update
    position = PositionUpdate(
        id=uuid.uuid4(),
        session_id=session.id,
        latitude=request.latitude,
        longitude=request.longitude,
        accuracy_meters=request.accuracy_meters,
        recorded_at=recorded_at,
    )
    db.add(position)
    await db.commit()
    
    return {"success": True, "message": "Position recorded"}


@router.post("/checkpoint", response_model=dict)
async def submit_checkpoint(
    request: CheckpointRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    User confirms passing a spatial marker (e.g., "I'm at the Kiosk").
    
    This creates a high-confidence data point for queue estimation.
    """
    # Get active session
    result = await db.execute(
        select(QueueSession)
        .where(
            QueueSession.user_id == current_user.id,
            QueueSession.result == None,
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=400,
            detail="No active queue session. Join the queue first.",
        )
    
    # Get the marker
    result = await db.execute(
        select(SpatialMarker).where(SpatialMarker.id == request.marker_id)
    )
    marker = result.scalar_one_or_none()
    
    if not marker:
        raise HTTPException(status_code=404, detail="Marker not found")
    
    # Create a parsed update from this checkpoint
    parsed_update = ParsedUpdate(
        club_id=marker.club_id,
        source="user",
        source_id=f"checkpoint-{session.id}-{marker.id}",
        raw_text=f"User checkpoint: {marker.name}",
        parsed_spatial_marker=marker.name,
        parsed_wait_minutes=marker.typical_wait_minutes,
        confidence=0.9,  # High confidence for user-confirmed checkpoints
        source_timestamp=datetime.utcnow(),
        author_name=current_user.display_name or current_user.email,
    )
    db.add(parsed_update)
    
    # Also create a position update at marker location
    position = PositionUpdate(
        id=uuid.uuid4(),
        session_id=session.id,
        latitude=float(marker.latitude),
        longitude=float(marker.longitude),
        recorded_at=datetime.utcnow(),
    )
    db.add(position)
    
    await db.commit()
    
    return {
        "success": True,
        "message": f"Checkpoint recorded: {marker.name}",
        "estimated_wait_minutes": marker.typical_wait_minutes,
    }


@router.post("/result", response_model=QueueSessionResponse)
async def submit_result(
    request: ResultRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Report queue result: admitted or rejected.
    
    This ends the queue session and records the outcome.
    """
    # Validate result
    valid_results = ['admitted', 'rejected']
    if request.result not in valid_results:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid result. Must be one of: {valid_results}",
        )
    
    # Get active session
    result = await db.execute(
        select(QueueSession)
        .options(selectinload(QueueSession.position_updates))
        .where(
            QueueSession.user_id == current_user.id,
            QueueSession.result == None,
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=400,
            detail="No active queue session.",
        )
    
    # Update session
    now = datetime.utcnow()
    session.result = request.result
    session.result_at = now
    
    if request.result == 'admitted':
        session.is_inside_club = True
    
    # Create a parsed update for this result
    result_db = await db.execute(
        select(Club).join(Event).where(Event.id == session.event_id)
    )
    club = result_db.scalar_one_or_none()
    
    if club:
        parsed_update = ParsedUpdate(
            club_id=club.id,
            source="user",
            source_id=f"result-{session.id}",
            raw_text=f"User reported: {request.result} after {session.wait_duration_minutes} min",
            parsed_wait_minutes=session.wait_duration_minutes,
            confidence=0.95,  # Very high confidence for direct user reports
            source_timestamp=now,
            author_name=current_user.display_name or current_user.email,
        )
        
        if request.result == 'rejected':
            # Note: We'd need to add these fields to ParsedUpdate model
            # For now, include in raw_text
            parsed_update.raw_text += " (rejected)"
        
        db.add(parsed_update)
    
    await db.commit()
    await db.refresh(session)
    
    return QueueSessionResponse(
        id=session.id,
        queue_type=session.queue_type,
        joined_at=session.joined_at.isoformat(),
        result=session.result,
        result_at=session.result_at.isoformat() if session.result_at else None,
        wait_duration_minutes=session.wait_duration_minutes,
        position_count=len(session.position_updates) if session.position_updates else 0,
    )


@router.post("/leave", response_model=dict)
async def leave_queue(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Leave the queue voluntarily (without admission result).
    
    Use this when user decides to leave without waiting for the result.
    """
    # Get active session
    result = await db.execute(
        select(QueueSession)
        .where(
            QueueSession.user_id == current_user.id,
            QueueSession.result == None,
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=400,
            detail="No active queue session.",
        )
    
    # Update session
    session.result = QueueResult.LEFT.value
    session.result_at = datetime.utcnow()
    
    await db.commit()
    
    return {"success": True, "message": "Left the queue"}


# =============================================================================
# External Source Update Endpoints
# =============================================================================

@router.post("/reddit-update", response_model=UpdateResponse)
async def receive_reddit_update(
    request: RawUpdateRequest,
    db: AsyncSession = Depends(get_db),
    x_source: Optional[str] = Header(None, alias="X-Source"),
):
    """
    Receive queue updates from the KlubFlow Devvit app.
    """
    if x_source != "devvit-klubflow":
        raise HTTPException(status_code=403, detail="Invalid source")
    
    return await _process_update(request, db)


@router.post("/telegram-update", response_model=UpdateResponse)
async def receive_telegram_update(
    request: RawUpdateRequest,
    db: AsyncSession = Depends(get_db),
    x_source: Optional[str] = Header(None, alias="X-Source"),
):
    """
    Receive queue updates from the Telegram monitor.
    """
    if x_source != "telegram-klubflow":
        raise HTTPException(status_code=403, detail="Invalid source")
    
    return await _process_update(request, db)


async def _process_update(
    request: RawUpdateRequest,
    db: AsyncSession,
) -> UpdateResponse:
    """Process a raw queue update from any source."""
    # Get Berghain club
    result = await db.execute(
        select(Club).where(Club.slug == "berghain")
    )
    club = result.scalar_one_or_none()
    
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    
    # Check for duplicate
    existing = await db.execute(
        select(ParsedUpdate).where(
            ParsedUpdate.source == request.source,
            ParsedUpdate.source_id == request.source_id,
        )
    )
    if existing.scalar_one_or_none():
        return UpdateResponse(
            success=True,
            message="Update already recorded",
        )
    
    # Parse the message
    parsed = parse_queue_message(request.content, parent_text=request.parent_content)
    
    # Skip if nothing useful was parsed
    if parsed.confidence < 0.2:
        return UpdateResponse(
            success=False,
            message="No queue information found in message",
        )
    
    # Determine source timestamp
    if request.source_timestamp:
        try:
            source_ts = datetime.fromisoformat(
                request.source_timestamp.replace('Z', '+00:00')
            )
        except ValueError:
            source_ts = datetime.utcnow()
    else:
        source_ts = datetime.utcnow()
    
    # Create parsed update record
    parsed_update = ParsedUpdate(
        club_id=club.id,
        source=request.source,
        source_id=request.source_id,
        raw_text=request.content,
        parsed_wait_minutes=parsed.wait_minutes,
        parsed_queue_length=parsed.queue_length,
        parsed_spatial_marker=parsed.spatial_marker,
        confidence=parsed.confidence,
        source_timestamp=source_ts,
        author_name=request.author_name,
    )
    
    db.add(parsed_update)
    await db.commit()
    await db.refresh(parsed_update)
    
    return UpdateResponse(
        success=True,
        message="Update recorded and parsed successfully",
        update_id=str(parsed_update.id),
        parsed_wait_minutes=parsed.wait_minutes,
        parsed_queue_length=parsed.queue_length,
        parsed_spatial_marker=parsed.spatial_marker,
    )


# =============================================================================
# Queue Status Endpoint
# =============================================================================

@router.get("/status", response_model=QueueStatusResponse)
async def get_queue_status(
    club_slug: str = "berghain",
    db: AsyncSession = Depends(get_db),
):
    """
    Get aggregated queue status from all data sources.
    
    Combines data from Reddit, Telegram, and user submissions.
    """
    # Get club
    result = await db.execute(
        select(Club).where(Club.slug == club_slug)
    )
    club = result.scalar_one_or_none()
    
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    
    # Get recent parsed updates (last 30 minutes)
    thirty_min_ago = datetime.utcnow() - timedelta(minutes=30)
    
    result = await db.execute(
        select(ParsedUpdate)
        .where(
            ParsedUpdate.club_id == club.id,
            ParsedUpdate.created_at >= thirty_min_ago,
            ParsedUpdate.is_outlier == False,
        )
        .order_by(ParsedUpdate.created_at.desc())
    )
    recent_updates = result.scalars().all()
    
    if not recent_updates:
        return QueueStatusResponse(
            estimated_wait_minutes=None,
            confidence="low",
            data_points=0,
            last_update=None,
            spatial_marker=None,
            queue_length=None,
            sources={},
        )
    
    # Aggregate wait times
    wait_times = []
    for u in recent_updates:
        if u.parsed_wait_minutes:
            wait_times.append(u.parsed_wait_minutes)
        elif u.parsed_spatial_marker:
            est = estimate_wait_from_spatial_marker(u.parsed_spatial_marker)
            if est:
                wait_times.append(est)
        elif u.parsed_queue_length:
            est = estimate_wait_from_queue_length(u.parsed_queue_length)
            if est:
                wait_times.append(est)
    
    avg_wait = round(sum(wait_times) / len(wait_times)) if wait_times else None
    
    # Get most recent spatial marker and queue length
    spatial_markers = [u.parsed_spatial_marker for u in recent_updates if u.parsed_spatial_marker]
    queue_lengths = [u.parsed_queue_length for u in recent_updates if u.parsed_queue_length]
    
    latest_marker = spatial_markers[0] if spatial_markers else None
    latest_length = queue_lengths[0] if queue_lengths else None
    
    # Count sources
    source_counts = {}
    for u in recent_updates:
        source_counts[u.source] = source_counts.get(u.source, 0) + 1
    
    # Determine confidence
    data_points = len(recent_updates)
    source_count = len(source_counts)
    
    if data_points >= 5 and source_count >= 2:
        confidence = "high"
    elif data_points >= 3 or (data_points >= 2 and source_count >= 2):
        confidence = "medium"
    else:
        confidence = "low"
    
    return QueueStatusResponse(
        estimated_wait_minutes=avg_wait,
        confidence=confidence,
        data_points=data_points,
        last_update=recent_updates[0].created_at.isoformat() if recent_updates else None,
        spatial_marker=latest_marker,
        queue_length=latest_length,
        sources=source_counts,
    )

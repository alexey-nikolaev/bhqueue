"""
Queue API endpoints.
Handles queue updates from Reddit (Devvit), Telegram, and user submissions.
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Club, ParsedUpdate
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

class RawUpdateRequest(BaseModel):
    """
    Raw update from external sources (Reddit, Telegram).
    
    The backend handles all parsing - sources just send raw text.
    Supports context-aware parsing via parent_content field.
    """
    source: str  # 'reddit', 'telegram'
    source_id: str  # Original message/comment ID
    content: str  # Raw message text
    parent_content: Optional[str] = None  # Parent/replied-to message for context
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
# Endpoints
# =============================================================================

@router.post("/reddit-update", response_model=UpdateResponse)
async def receive_reddit_update(
    request: RawUpdateRequest,
    db: AsyncSession = Depends(get_db),
    x_source: Optional[str] = Header(None, alias="X-Source"),
):
    """
    Receive queue updates from the KlubFlow Devvit app.
    
    The Devvit app sends raw comment/post text, and we parse it here.
    """
    # Verify the request comes from our Devvit app
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
    """
    Process a raw queue update from any source.
    
    1. Validates the request
    2. Parses the text using unified parser
    3. Stores the parsed update
    """
    # Get Berghain club
    result = await db.execute(
        select(Club).where(Club.slug == "berghain")
    )
    club = result.scalar_one_or_none()
    
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    
    # Check if we're during a Klubnacht (optional - we might want to store data anyway)
    current_event = get_current_klubnacht()
    
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
    
    # Parse the message using our unified parser (with optional context)
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


@router.get("/status", response_model=QueueStatusResponse)
async def get_queue_status(
    club_slug: str = "berghain",
    db: AsyncSession = Depends(get_db),
):
    """
    Get aggregated queue status from all data sources.
    
    Combines data from Reddit, Telegram, and user submissions
    to estimate current queue conditions.
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
    
    # Aggregate wait times (prefer explicit times, fall back to estimates)
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
    
    # Determine confidence based on data points and source diversity
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

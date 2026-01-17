"""
Club API endpoints.

Public endpoints for mobile apps to fetch club data, queues, and markers.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Club, Queue, SpatialMarker
from app.services.event_service import get_club_status

router = APIRouter()


# =============================================================================
# Response Schemas
# =============================================================================

class ClubResponse(BaseModel):
    """Club information."""
    id: uuid.UUID
    name: str
    slug: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: str
    is_active: bool

    class Config:
        from_attributes = True


class QueueResponse(BaseModel):
    """Queue type information."""
    id: uuid.UUID
    queue_type: str
    name: str
    description: Optional[str] = None
    display_order: int

    class Config:
        from_attributes = True


class SpatialMarkerResponse(BaseModel):
    """Spatial marker information."""
    id: uuid.UUID
    queue_id: Optional[uuid.UUID] = None
    name: str
    aliases: Optional[list[str]] = None
    latitude: float
    longitude: float
    distance_from_door_meters: int
    typical_wait_minutes: Optional[int] = None
    display_order: int

    class Config:
        from_attributes = True


# =============================================================================
# Club Endpoints
# =============================================================================

@router.get("", response_model=list[ClubResponse])
async def list_clubs(
    db: AsyncSession = Depends(get_db),
):
    """
    List all active clubs.
    """
    result = await db.execute(
        select(Club).where(Club.is_active == True).order_by(Club.name)
    )
    clubs = result.scalars().all()
    return clubs


@router.get("/{slug}", response_model=ClubResponse)
async def get_club(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific club by slug.
    """
    result = await db.execute(
        select(Club).where(Club.slug == slug)
    )
    club = result.scalar_one_or_none()
    
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    
    return club


@router.get("/{slug}/status")
async def get_club_status_endpoint(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get current status of a club.
    
    Returns whether the club is open, current event info,
    and next event if closed.
    """
    # Verify club exists
    result = await db.execute(
        select(Club).where(Club.slug == slug)
    )
    club = result.scalar_one_or_none()
    
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    
    # Currently only Berghain has status logic
    if slug == "berghain":
        return get_club_status()
    
    return {"message": "Status not available for this club"}


# =============================================================================
# Queue Endpoints (Public - for mobile apps)
# =============================================================================

@router.get("/{slug}/queues", response_model=list[QueueResponse])
async def list_club_queues(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """
    List all queue types for a club.
    
    For example, Berghain has:
    - Main queue (regular entry)
    - Guestlist queue
    - Re-entry queue
    """
    # Verify club exists
    result = await db.execute(
        select(Club).where(Club.slug == slug)
    )
    club = result.scalar_one_or_none()
    
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    
    # Get queues
    result = await db.execute(
        select(Queue)
        .where(Queue.club_id == club.id)
        .order_by(Queue.display_order)
    )
    queues = result.scalars().all()
    return queues


# =============================================================================
# Spatial Marker Endpoints (Public - for mobile apps)
# =============================================================================

@router.get("/{slug}/markers", response_model=list[SpatialMarkerResponse])
async def list_club_markers(
    slug: str,
    queue_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    List all spatial markers for a club.
    
    Optionally filter by queue_type (main, guestlist, reentry).
    
    Mobile apps use this to:
    - Show landmarks on the map
    - Let users check in at markers
    - Display estimated wait times
    """
    # Verify club exists
    result = await db.execute(
        select(Club).where(Club.slug == slug)
    )
    club = result.scalar_one_or_none()
    
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    
    # Build query
    query = select(SpatialMarker).where(SpatialMarker.club_id == club.id)
    
    if queue_type:
        query = query.join(Queue).where(Queue.queue_type == queue_type)
    
    query = query.order_by(SpatialMarker.display_order)
    
    result = await db.execute(query)
    markers = result.scalars().all()
    return markers


@router.get("/{slug}/markers/{marker_id}", response_model=SpatialMarkerResponse)
async def get_club_marker(
    slug: str,
    marker_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific marker by ID.
    """
    result = await db.execute(
        select(SpatialMarker)
        .join(Club)
        .where(Club.slug == slug, SpatialMarker.id == marker_id)
    )
    marker = result.scalar_one_or_none()
    
    if not marker:
        raise HTTPException(status_code=404, detail="Marker not found")
    
    return marker


# =============================================================================
# Legacy endpoint (for backwards compatibility)
# =============================================================================

@router.get("/berghain/status")
async def get_berghain_status_legacy(db: AsyncSession = Depends(get_db)):
    """
    Legacy endpoint - redirects to /{slug}/status
    """
    return await get_club_status_endpoint("berghain", db)

"""
Admin API endpoints for managing application data.

These endpoints allow updating spatial markers and queues without redeploying.

**Authentication required:**
- Authenticated user with `is_admin=True`, OR
- Valid `X-Admin-API-Key` header
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import verify_admin_access
from app.database import get_db
from app.models import SpatialMarker, Club, Queue, QueueType, User
from app.services.queue_parser import refresh_marker_cache

router = APIRouter()


# ============================================================================
# Schemas
# ============================================================================

# --- Queue Schemas ---

class QueueBase(BaseModel):
    """Base schema for queue data."""
    queue_type: str
    name: str
    description: Optional[str] = None
    display_order: int = 0


class QueueCreate(QueueBase):
    """Schema for creating a new queue."""
    club_id: uuid.UUID


class QueueUpdate(BaseModel):
    """Schema for updating a queue (all fields optional)."""
    name: Optional[str] = None
    description: Optional[str] = None
    display_order: Optional[int] = None


class QueueResponse(QueueBase):
    """Schema for queue response."""
    id: uuid.UUID
    club_id: uuid.UUID

    class Config:
        from_attributes = True


class QueueWithMarkersResponse(QueueResponse):
    """Schema for queue response with markers included."""
    markers_count: int = 0


# --- Spatial Marker Schemas ---

class SpatialMarkerBase(BaseModel):
    """Base schema for spatial marker data."""
    name: str
    aliases: Optional[list[str]] = None
    latitude: float
    longitude: float
    distance_from_door_meters: int
    typical_wait_minutes: Optional[int] = None
    display_order: int = 0


class SpatialMarkerCreate(SpatialMarkerBase):
    """Schema for creating a new spatial marker."""
    club_id: uuid.UUID
    queue_id: Optional[uuid.UUID] = None


class SpatialMarkerUpdate(BaseModel):
    """Schema for updating a spatial marker (all fields optional)."""
    name: Optional[str] = None
    aliases: Optional[list[str]] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_from_door_meters: Optional[int] = None
    typical_wait_minutes: Optional[int] = None
    display_order: Optional[int] = None
    queue_id: Optional[uuid.UUID] = None


class QueueInfo(BaseModel):
    """Minimal queue info for embedding in marker response."""
    id: uuid.UUID
    queue_type: str
    name: str

    class Config:
        from_attributes = True


class SpatialMarkerResponse(SpatialMarkerBase):
    """Schema for spatial marker response."""
    id: uuid.UUID
    club_id: uuid.UUID
    queue_id: Optional[uuid.UUID] = None
    queue: Optional[QueueInfo] = None

    class Config:
        from_attributes = True


# ============================================================================
# Queue Endpoints
# ============================================================================

@router.get("/queues", response_model=list[QueueWithMarkersResponse])
async def list_queues(
    club_slug: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _admin: Optional[User] = Depends(verify_admin_access),
):
    """
    List all queues, optionally filtered by club.
    
    - **club_slug**: Filter by club (e.g., "berghain")
    """
    query = select(Queue).options(selectinload(Queue.spatial_markers))
    
    if club_slug:
        query = query.join(Club).where(Club.slug == club_slug)
    
    query = query.order_by(Queue.display_order)
    
    result = await db.execute(query)
    queues = result.scalars().all()
    
    # Add markers_count
    response = []
    for q in queues:
        queue_dict = {
            "id": q.id,
            "club_id": q.club_id,
            "queue_type": q.queue_type,
            "name": q.name,
            "description": q.description,
            "display_order": q.display_order,
            "markers_count": len(q.spatial_markers) if q.spatial_markers else 0,
        }
        response.append(queue_dict)
    
    return response


@router.get("/queues/{queue_id}", response_model=QueueResponse)
async def get_queue(
    queue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: Optional[User] = Depends(verify_admin_access),
):
    """Get a specific queue by ID."""
    result = await db.execute(
        select(Queue).where(Queue.id == queue_id)
    )
    queue = result.scalar_one_or_none()
    
    if not queue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue not found",
        )
    
    return queue


@router.post("/queues", response_model=QueueResponse, status_code=status.HTTP_201_CREATED)
async def create_queue(
    data: QueueCreate,
    db: AsyncSession = Depends(get_db),
    _admin: Optional[User] = Depends(verify_admin_access),
):
    """
    Create a new queue for a club.
    
    Valid queue_type values: "main", "guestlist", "reentry"
    """
    # Verify club exists
    result = await db.execute(select(Club).where(Club.id == data.club_id))
    club = result.scalar_one_or_none()
    if not club:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Club not found",
        )
    
    # Validate queue_type
    valid_types = [t.value for t in QueueType]
    if data.queue_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid queue_type. Must be one of: {valid_types}",
        )
    
    queue = Queue(
        id=uuid.uuid4(),
        club_id=data.club_id,
        queue_type=data.queue_type,
        name=data.name,
        description=data.description,
        display_order=data.display_order,
    )
    
    db.add(queue)
    await db.commit()
    await db.refresh(queue)
    
    return queue


@router.patch("/queues/{queue_id}", response_model=QueueResponse)
async def update_queue(
    queue_id: uuid.UUID,
    data: QueueUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: Optional[User] = Depends(verify_admin_access),
):
    """Update a queue."""
    result = await db.execute(
        select(Queue).where(Queue.id == queue_id)
    )
    queue = result.scalar_one_or_none()
    
    if not queue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue not found",
        )
    
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(queue, field, value)
    
    await db.commit()
    await db.refresh(queue)
    
    return queue


@router.delete("/queues/{queue_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_queue(
    queue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: Optional[User] = Depends(verify_admin_access),
):
    """
    Delete a queue.
    
    Note: This will NOT delete associated markers, but will set their queue_id to NULL.
    """
    result = await db.execute(
        select(Queue).where(Queue.id == queue_id)
    )
    queue = result.scalar_one_or_none()
    
    if not queue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue not found",
        )
    
    await db.delete(queue)
    await db.commit()


# ============================================================================
# Spatial Marker Endpoints
# ============================================================================

@router.get("/markers", response_model=list[SpatialMarkerResponse])
async def list_spatial_markers(
    club_slug: Optional[str] = None,
    queue_id: Optional[uuid.UUID] = None,
    queue_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _admin: Optional[User] = Depends(verify_admin_access),
):
    """
    List all spatial markers with optional filters.
    
    - **club_slug**: Filter by club (e.g., "berghain")
    - **queue_id**: Filter by specific queue UUID
    - **queue_type**: Filter by queue type ("main", "guestlist", "reentry")
    """
    query = select(SpatialMarker).options(selectinload(SpatialMarker.queue))
    
    if club_slug:
        query = query.join(Club, SpatialMarker.club_id == Club.id).where(Club.slug == club_slug)
    
    if queue_id:
        query = query.where(SpatialMarker.queue_id == queue_id)
    elif queue_type:
        query = query.join(Queue, SpatialMarker.queue_id == Queue.id).where(Queue.queue_type == queue_type)
    
    query = query.order_by(SpatialMarker.display_order)
    
    result = await db.execute(query)
    markers = result.scalars().all()
    return markers


@router.get("/markers/{marker_id}", response_model=SpatialMarkerResponse)
async def get_spatial_marker(
    marker_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: Optional[User] = Depends(verify_admin_access),
):
    """Get a specific spatial marker by ID."""
    result = await db.execute(
        select(SpatialMarker)
        .options(selectinload(SpatialMarker.queue))
        .where(SpatialMarker.id == marker_id)
    )
    marker = result.scalar_one_or_none()
    
    if not marker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Spatial marker not found",
        )
    
    return marker


@router.post("/markers", response_model=SpatialMarkerResponse, status_code=status.HTTP_201_CREATED)
async def create_spatial_marker(
    data: SpatialMarkerCreate,
    db: AsyncSession = Depends(get_db),
    _admin: Optional[User] = Depends(verify_admin_access),
):
    """
    Create a new spatial marker.
    
    The parser cache will be automatically refreshed.
    """
    # Verify club exists
    result = await db.execute(select(Club).where(Club.id == data.club_id))
    club = result.scalar_one_or_none()
    if not club:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Club not found",
        )
    
    # Verify queue exists if provided
    if data.queue_id:
        result = await db.execute(select(Queue).where(Queue.id == data.queue_id))
        queue = result.scalar_one_or_none()
        if not queue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Queue not found",
            )
    
    marker = SpatialMarker(
        id=uuid.uuid4(),
        club_id=data.club_id,
        queue_id=data.queue_id,
        name=data.name,
        aliases=data.aliases,
        latitude=data.latitude,
        longitude=data.longitude,
        distance_from_door_meters=data.distance_from_door_meters,
        typical_wait_minutes=data.typical_wait_minutes,
        display_order=data.display_order,
    )
    
    db.add(marker)
    await db.commit()
    await db.refresh(marker)
    
    # Load queue relationship for response
    if marker.queue_id:
        result = await db.execute(
            select(SpatialMarker)
            .options(selectinload(SpatialMarker.queue))
            .where(SpatialMarker.id == marker.id)
        )
        marker = result.scalar_one()
    
    # Refresh parser cache
    refresh_marker_cache()
    
    return marker


@router.patch("/markers/{marker_id}", response_model=SpatialMarkerResponse)
async def update_spatial_marker(
    marker_id: uuid.UUID,
    data: SpatialMarkerUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: Optional[User] = Depends(verify_admin_access),
):
    """
    Update a spatial marker.
    
    Only provided fields will be updated. The parser cache will be automatically refreshed.
    
    **Use this to tune wait time estimates based on real data:**
    ```
    PATCH /api/admin/markers/{id}
    {"typical_wait_minutes": 70}
    ```
    """
    result = await db.execute(
        select(SpatialMarker).where(SpatialMarker.id == marker_id)
    )
    marker = result.scalar_one_or_none()
    
    if not marker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Spatial marker not found",
        )
    
    # Verify queue exists if being updated
    update_data = data.model_dump(exclude_unset=True)
    if "queue_id" in update_data and update_data["queue_id"]:
        result = await db.execute(select(Queue).where(Queue.id == update_data["queue_id"]))
        queue = result.scalar_one_or_none()
        if not queue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Queue not found",
            )
    
    # Update only provided fields
    for field, value in update_data.items():
        setattr(marker, field, value)
    
    await db.commit()
    
    # Reload with queue relationship
    result = await db.execute(
        select(SpatialMarker)
        .options(selectinload(SpatialMarker.queue))
        .where(SpatialMarker.id == marker_id)
    )
    marker = result.scalar_one()
    
    # Refresh parser cache
    refresh_marker_cache()
    
    return marker


@router.delete("/markers/{marker_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_spatial_marker(
    marker_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: Optional[User] = Depends(verify_admin_access),
):
    """
    Delete a spatial marker.
    
    The parser cache will be automatically refreshed.
    """
    result = await db.execute(
        select(SpatialMarker).where(SpatialMarker.id == marker_id)
    )
    marker = result.scalar_one_or_none()
    
    if not marker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Spatial marker not found",
        )
    
    await db.delete(marker)
    await db.commit()
    
    # Refresh parser cache
    refresh_marker_cache()


@router.post("/markers/refresh-cache", status_code=status.HTTP_204_NO_CONTENT)
async def force_refresh_cache(
    _admin: Optional[User] = Depends(verify_admin_access),
):
    """
    Force refresh the parser's marker cache.
    
    Useful after bulk database changes.
    """
    refresh_marker_cache()

"""
Club API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Club
from app.services.event_service import get_club_status

router = APIRouter()


@router.get("/berghain/status")
async def get_berghain_status(db: AsyncSession = Depends(get_db)):
    """
    Get current status of Berghain.
    
    Returns whether the club is open, current event info,
    and next event if closed.
    """
    # Verify Berghain exists in database
    result = await db.execute(
        select(Club).where(Club.slug == "berghain")
    )
    club = result.scalar_one_or_none()
    
    if not club:
        raise HTTPException(status_code=404, detail="Club not found. Run seed script first.")
    
    return get_club_status()

"""
Event service - handles event scheduling and lookup.

For Klubnacht, events are generated on-the-fly based on the fixed schedule
(Saturday 23:59 - Monday 08:00 Berlin time, queue opens 21:00).

Events are only persisted to the database when:
- A user joins a queue (creates the event record)
- We have parsed data for that weekend
- It's a special/non-standard event
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Club, Event
from app.utils.timezone import BERLIN_TZ, to_utc


# Klubnacht schedule (Berlin time)
KLUBNACHT_QUEUE_OPENS_HOUR = 21
KLUBNACHT_QUEUE_OPENS_MINUTE = 0
KLUBNACHT_START_HOUR = 23
KLUBNACHT_START_MINUTE = 59
KLUBNACHT_END_HOUR = 8
KLUBNACHT_END_MINUTE = 0


def get_klubnacht_times_for_date(saturday_date) -> tuple[datetime, datetime, datetime]:
    """
    Calculate Klubnacht times for a given Saturday.
    
    Args:
        saturday_date: A date object for the Saturday
        
    Returns:
        Tuple of (queue_opens, starts_at, ends_at) in UTC
    """
    # Create Berlin-timezone datetimes
    queue_opens_berlin = BERLIN_TZ.localize(
        datetime.combine(
            saturday_date,
            datetime.min.time().replace(
                hour=KLUBNACHT_QUEUE_OPENS_HOUR,
                minute=KLUBNACHT_QUEUE_OPENS_MINUTE
            )
        )
    )
    starts_at_berlin = BERLIN_TZ.localize(
        datetime.combine(
            saturday_date,
            datetime.min.time().replace(
                hour=KLUBNACHT_START_HOUR,
                minute=KLUBNACHT_START_MINUTE
            )
        )
    )
    # Ends Monday morning (2 days later)
    ends_at_berlin = BERLIN_TZ.localize(
        datetime.combine(
            saturday_date + timedelta(days=2),
            datetime.min.time().replace(
                hour=KLUBNACHT_END_HOUR,
                minute=KLUBNACHT_END_MINUTE
            )
        )
    )
    
    return (
        to_utc(queue_opens_berlin),
        to_utc(starts_at_berlin),
        to_utc(ends_at_berlin),
    )


def get_current_or_next_klubnacht_saturday() -> tuple[datetime, bool]:
    """
    Get the Saturday date for the current or next Klubnacht.
    
    Returns:
        Tuple of (saturday_date, is_currently_active)
    """
    now_berlin = datetime.now(BERLIN_TZ)
    today = now_berlin.date()
    weekday = today.weekday()  # Monday=0, Saturday=5, Sunday=6
    
    # Calculate the most recent Saturday
    if weekday == 5:  # Saturday
        recent_saturday = today
    elif weekday == 6:  # Sunday
        recent_saturday = today - timedelta(days=1)
    else:  # Monday-Friday
        recent_saturday = today - timedelta(days=weekday + 2)
    
    # Check if we're within the current Klubnacht window
    queue_opens, starts_at, ends_at = get_klubnacht_times_for_date(recent_saturday)
    now_utc = to_utc(now_berlin)
    
    if queue_opens <= now_utc <= ends_at:
        # We're in an active Klubnacht
        return recent_saturday, True
    
    # Find next Saturday
    days_until_saturday = (5 - weekday) % 7
    if days_until_saturday == 0:
        days_until_saturday = 7  # Next week's Saturday
    next_saturday = today + timedelta(days=days_until_saturday)
    
    return next_saturday, False


def get_current_klubnacht_times() -> Optional[tuple[datetime, datetime, datetime]]:
    """
    Get times for the currently active Klubnacht, if any.
    
    Returns:
        Tuple of (queue_opens, starts_at, ends_at) in UTC, or None if no active event
    """
    saturday, is_active = get_current_or_next_klubnacht_saturday()
    if is_active:
        return get_klubnacht_times_for_date(saturday)
    return None


def get_next_klubnacht_times() -> tuple[datetime, datetime, datetime]:
    """
    Get times for the next Klubnacht (current if active, otherwise upcoming).
    
    Returns:
        Tuple of (queue_opens, starts_at, ends_at) in UTC
    """
    saturday, _ = get_current_or_next_klubnacht_saturday()
    return get_klubnacht_times_for_date(saturday)


async def get_or_create_current_event(
    db: AsyncSession,
    club: Club,
) -> Optional[Event]:
    """
    Get the current active event, creating it if necessary.
    
    Only creates an event record if Klubnacht is currently active
    (queue is open or party is running).
    
    Args:
        db: Database session
        club: The club (Berghain)
        
    Returns:
        Event record, or None if no active event
    """
    current_times = get_current_klubnacht_times()
    if current_times is None:
        return None
    
    queue_opens, starts_at, ends_at = current_times
    
    # Check if event already exists
    result = await db.execute(
        select(Event).where(
            Event.club_id == club.id,
            Event.starts_at == starts_at,
        )
    )
    event = result.scalar_one_or_none()
    
    if event:
        return event
    
    # Create new event record
    event = Event(
        id=uuid.uuid4(),
        club_id=club.id,
        name="Klubnacht",
        queue_opens_at=queue_opens,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    db.add(event)
    await db.flush()
    
    return event


def is_klubnacht_active() -> bool:
    """Check if Klubnacht is currently active (queue open or party running)."""
    _, is_active = get_current_or_next_klubnacht_saturday()
    return is_active


def get_club_status() -> dict:
    """
    Get the current status of the club.
    
    Returns:
        Dict with status info for the frontend
    """
    saturday, is_active = get_current_or_next_klubnacht_saturday()
    
    if is_active:
        queue_opens, starts_at, ends_at = get_klubnacht_times_for_date(saturday)
        now_utc = to_utc(datetime.now(BERLIN_TZ))
        
        if now_utc < starts_at:
            phase = "queue_open"
        else:
            phase = "party_running"
        
        return {
            "is_open": True,
            "event_name": "Klubnacht",
            "phase": phase,
            "queue_opens_at": queue_opens.isoformat() + "Z",
            "starts_at": starts_at.isoformat() + "Z",
            "ends_at": ends_at.isoformat() + "Z",
        }
    else:
        # Club is closed, return next event info
        queue_opens, starts_at, ends_at = get_klubnacht_times_for_date(saturday)
        return {
            "is_open": False,
            "event_name": None,
            "phase": "closed",
            "next_event": {
                "name": "Klubnacht",
                "queue_opens_at": queue_opens.isoformat() + "Z",
                "starts_at": starts_at.isoformat() + "Z",
                "ends_at": ends_at.isoformat() + "Z",
            }
        }

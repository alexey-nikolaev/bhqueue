"""
Timezone utilities for converting between UTC and local times.

All database timestamps are stored in UTC. These utilities help
convert to/from local timezone (Berlin) for display and input.
"""

from datetime import datetime
from typing import Optional

import pytz

# Default timezone for clubs (Berghain is in Berlin)
BERLIN_TZ = pytz.timezone("Europe/Berlin")
UTC_TZ = pytz.UTC


def utc_now() -> datetime:
    """Get current time in UTC (timezone-aware)."""
    return datetime.now(UTC_TZ)


def to_utc(local_dt: datetime, timezone: str = "Europe/Berlin") -> datetime:
    """
    Convert a local datetime to UTC.
    
    Args:
        local_dt: Datetime in local timezone (can be naive or aware)
        timezone: Timezone name (default: Europe/Berlin)
    
    Returns:
        Timezone-naive datetime in UTC (for database storage)
    """
    tz = pytz.timezone(timezone)
    
    if local_dt.tzinfo is None:
        # Naive datetime - assume it's in the specified timezone
        local_dt = tz.localize(local_dt)
    
    # Convert to UTC and remove timezone info for database storage
    utc_dt = local_dt.astimezone(UTC_TZ)
    return utc_dt.replace(tzinfo=None)


def from_utc(utc_dt: datetime, timezone: str = "Europe/Berlin") -> datetime:
    """
    Convert a UTC datetime to local timezone.
    
    Args:
        utc_dt: Datetime in UTC (can be naive or aware)
        timezone: Target timezone name (default: Europe/Berlin)
    
    Returns:
        Timezone-aware datetime in local timezone
    """
    tz = pytz.timezone(timezone)
    
    if utc_dt.tzinfo is None:
        # Naive datetime - assume it's UTC
        utc_dt = UTC_TZ.localize(utc_dt)
    
    return utc_dt.astimezone(tz)


def format_local_time(
    utc_dt: datetime,
    timezone: str = "Europe/Berlin",
    fmt: str = "%Y-%m-%d %H:%M"
) -> str:
    """
    Format a UTC datetime as a local time string.
    
    Args:
        utc_dt: Datetime in UTC
        timezone: Target timezone name
        fmt: strftime format string
    
    Returns:
        Formatted datetime string in local timezone
    """
    local_dt = from_utc(utc_dt, timezone)
    return local_dt.strftime(fmt)


def get_berlin_time(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
) -> datetime:
    """
    Create a Berlin datetime and convert to UTC for storage.
    
    Useful for creating event times like "Saturday 23:59 Berlin time".
    
    Returns:
        Timezone-naive datetime in UTC
    """
    berlin_dt = BERLIN_TZ.localize(
        datetime(year, month, day, hour, minute, second)
    )
    return berlin_dt.astimezone(UTC_TZ).replace(tzinfo=None)

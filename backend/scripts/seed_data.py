"""
Seed the database with initial data.

Run with: python -m scripts.seed_data
"""

import asyncio
import uuid
from datetime import datetime, timedelta

import pytz
from sqlalchemy import select

from app.database import async_session_maker, init_db
from app.models import Club, SpatialMarker


# Berghain building polygon (approximate)
# This is used to detect if a user's GPS is inside the club
BERGHAIN_POLYGON = {
    "type": "Polygon",
    "coordinates": [[
        [13.4430, 52.5112],
        [13.4438, 52.5112],
        [13.4438, 52.5105],
        [13.4430, 52.5105],
        [13.4430, 52.5112],
    ]]
}

# Spatial markers around Berghain
# Only the entrance is known for sure - other markers will be
# discovered by parsing Reddit/Telegram data from past Klubnachts
BERGHAIN_MARKERS = [
    {
        "name": "entrance",
        "aliases": ["door", "türsteher", "bouncer", "eingang"],
        "latitude": 52.5108,
        "longitude": 13.4434,
        "distance_from_door_meters": 0,
        "typical_wait_minutes": 5,
        "display_order": 1,
    },
    # Additional markers will be added from Reddit/Telegram parsing:
    # - Parse past Klubnacht threads for location references
    # - Identify frequently mentioned landmarks
    # - Map them to GPS coordinates and typical wait times
]


async def seed_berghain() -> None:
    """Seed Berghain club data."""
    async with async_session_maker() as session:
        # Check if Berghain already exists
        result = await session.execute(
            select(Club).where(Club.slug == "berghain")
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print("Berghain already exists, skipping club creation.")
            berghain = existing
        else:
            berghain = Club(
                id=uuid.uuid4(),
                name="Berghain",
                slug="berghain",
                address="Am Wriezener Bahnhof, 10243 Berlin, Germany",
                latitude=52.5108,
                longitude=13.4434,
                building_polygon=BERGHAIN_POLYGON,
                timezone="Europe/Berlin",
                is_active=True,
            )
            session.add(berghain)
            await session.flush()
            print(f"Created club: {berghain.name}")
        
        # Add spatial markers
        for marker_data in BERGHAIN_MARKERS:
            result = await session.execute(
                select(SpatialMarker).where(
                    SpatialMarker.club_id == berghain.id,
                    SpatialMarker.name == marker_data["name"],
                )
            )
            if result.scalar_one_or_none():
                print(f"  Marker '{marker_data['name']}' already exists, skipping.")
                continue
            
            marker = SpatialMarker(
                id=uuid.uuid4(),
                club_id=berghain.id,
                **marker_data,
            )
            session.add(marker)
            print(f"  Created marker: {marker_data['name']}")
        
        await session.commit()
        
        # Note: Events are now created on-the-fly when needed
        # (when a user joins queue or when we parse data for that weekend)
        # See app/services/event_service.py
        print("\nSeed data complete!")


async def main():
    """Main entry point."""
    print("Initializing database...")
    await init_db()
    
    print("\nSeeding Berghain data...")
    await seed_berghain()


if __name__ == "__main__":
    asyncio.run(main())

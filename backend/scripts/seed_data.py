"""
Seed the database with initial data.

Run with: python -m scripts.seed_data
"""

import asyncio
import uuid
from datetime import datetime, timedelta

import pytz
from sqlalchemy import select, update

from app.database import async_session_maker, init_db
from app.models import Club, Queue, QueueType, SpatialMarker


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

# Queue definitions for Berghain
BERGHAIN_QUEUES = [
    {
        "queue_type": QueueType.MAIN,
        "name": "Main Queue",
        "description": "Regular entry queue along Am Wriezener Bahnhof",
        "display_order": 1,
    },
    {
        "queue_type": QueueType.GUESTLIST,
        "name": "Guestlist Queue",
        "description": "Guestlist queue along the face of the building",
        "display_order": 2,
    },
    {
        "queue_type": QueueType.REENTRY,
        "name": "Re-entry Queue",
        "description": "Re-entry queue for people with wristbands",
        "display_order": 3,
    },
]

# Spatial markers around Berghain
# Based on r/Berghain_Community FAQ:
# Main queue: snake → concrete blocks → magic cube → kiosk → wriezener karree → metro sign
# GL/Re-entry: barriers → love sculpture → garten door → ATM → park
#
# Wait times are estimates that can be tuned based on real data.
# Coordinates are approximate - refine with GPS data collection.

# Main queue markers
MAIN_QUEUE_MARKERS = [
    {
        "name": "Door",
        "aliases": ["door", "entrance", "türsteher", "bouncer", "eingang"],
        "latitude": 52.5108,
        "longitude": 13.4434,
        "distance_from_door_meters": 0,
        "typical_wait_minutes": 0,
        "display_order": 1,
    },
    {
        "name": "Snake",
        "aliases": ["snake", "schlange"],
        "latitude": 52.5107,
        "longitude": 13.4432,
        "distance_from_door_meters": 30,
        "typical_wait_minutes": 15,
        "display_order": 2,
    },
    {
        "name": "Concrete blocks",
        "aliases": ["concrete", "concrete block", "concrete blocks", "betonblöcke"],
        "latitude": 52.5106,
        "longitude": 13.4430,
        "distance_from_door_meters": 60,
        "typical_wait_minutes": 25,
        "display_order": 3,
    },
    {
        "name": "Magic Cube",
        "aliases": ["magic cube", "cube", "würfel"],
        "latitude": 52.5105,
        "longitude": 13.4428,
        "distance_from_door_meters": 100,
        "typical_wait_minutes": 40,
        "display_order": 4,
    },
    {
        "name": "Kiosk",
        "aliases": ["kiosk", "snack", "snack shop"],
        "latitude": 52.5103,
        "longitude": 13.4425,
        "distance_from_door_meters": 150,
        "typical_wait_minutes": 55,
        "display_order": 5,
    },
    {
        "name": "Past Kiosk",
        "aliases": ["past kiosk", "behind kiosk", "nach kiosk"],
        "latitude": 52.5101,
        "longitude": 13.4422,
        "distance_from_door_meters": 200,
        "typical_wait_minutes": 70,
        "display_order": 6,
    },
    {
        "name": "Späti",
        "aliases": ["späti", "spati", "spätkauf"],
        "latitude": 52.5099,
        "longitude": 13.4418,
        "distance_from_door_meters": 280,
        "typical_wait_minutes": 90,
        "display_order": 7,
    },
    {
        "name": "Bridge",
        "aliases": ["bridge", "brücke"],
        "latitude": 52.5097,
        "longitude": 13.4414,
        "distance_from_door_meters": 350,
        "typical_wait_minutes": 100,
        "display_order": 8,
    },
    {
        "name": "Around the block",
        "aliases": ["around the block", "um die ecke", "corner"],
        "latitude": 52.5095,
        "longitude": 13.4410,
        "distance_from_door_meters": 400,
        "typical_wait_minutes": 120,
        "display_order": 9,
    },
    {
        "name": "Wriezener Straße",
        "aliases": ["wriezener", "am wriezener", "wriezener straße", "wriezener strasse"],
        "latitude": 52.5092,
        "longitude": 13.4405,
        "distance_from_door_meters": 500,
        "typical_wait_minutes": 140,
        "display_order": 10,
    },
    {
        "name": "Wriezener Karree",
        "aliases": ["wriezener karree", "karree"],
        "latitude": 52.5089,
        "longitude": 13.4400,
        "distance_from_door_meters": 550,
        "typical_wait_minutes": 150,
        "display_order": 11,
    },
    {
        "name": "Metro sign",
        "aliases": ["metro", "metro sign", "u-bahn", "ubahn"],
        "latitude": 52.5085,
        "longitude": 13.4395,
        "distance_from_door_meters": 650,
        "typical_wait_minutes": 180,
        "display_order": 12,
    },
]

# Guestlist / Re-entry queue markers (shared between GL and re-entry)
GL_QUEUE_MARKERS = [
    {
        "name": "Barriers (GL)",
        "aliases": ["barrier", "barriers", "gl barrier", "guestlist barrier"],
        "latitude": 52.5109,
        "longitude": 13.4436,
        "distance_from_door_meters": 20,
        "typical_wait_minutes": 5,
        "display_order": 1,
    },
    {
        "name": "Love sculpture (GL)",
        "aliases": ["love", "love sculpture", "love skulptur"],
        "latitude": 52.5110,
        "longitude": 13.4438,
        "distance_from_door_meters": 40,
        "typical_wait_minutes": 15,
        "display_order": 2,
    },
    {
        "name": "Garten door (GL)",
        "aliases": ["garten", "garten door", "garden", "garden door"],
        "latitude": 52.5111,
        "longitude": 13.4440,
        "distance_from_door_meters": 60,
        "typical_wait_minutes": 25,
        "display_order": 3,
    },
    {
        "name": "ATM (GL)",
        "aliases": ["atm", "geldautomat", "cash machine"],
        "latitude": 52.5112,
        "longitude": 13.4442,
        "distance_from_door_meters": 100,
        "typical_wait_minutes": 35,
        "display_order": 4,
    },
    {
        "name": "Park (GL)",
        "aliases": ["park", "gl park"],
        "latitude": 52.5114,
        "longitude": 13.4445,
        "distance_from_door_meters": 150,
        "typical_wait_minutes": 45,
        "display_order": 5,
    },
]


async def seed_berghain() -> None:
    """Seed Berghain club data with queues and markers."""
    async with async_session_maker() as session:
        # ====================================================================
        # 1. Create or get Berghain club
        # ====================================================================
        result = await session.execute(
            select(Club).where(Club.slug == "berghain")
        )
        berghain = result.scalar_one_or_none()
        
        if berghain:
            print("✓ Berghain club exists")
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
            print(f"✓ Created club: {berghain.name}")
        
        # ====================================================================
        # 2. Create queues
        # ====================================================================
        print("\nQueues:")
        queues = {}
        
        for queue_data in BERGHAIN_QUEUES:
            queue_type = queue_data["queue_type"]
            
            result = await session.execute(
                select(Queue).where(
                    Queue.club_id == berghain.id,
                    Queue.queue_type == queue_type.value,
                )
            )
            existing_queue = result.scalar_one_or_none()
            
            if existing_queue:
                print(f"  ✓ {queue_data['name']} exists")
                queues[queue_type] = existing_queue
            else:
                queue = Queue(
                    id=uuid.uuid4(),
                    club_id=berghain.id,
                    queue_type=queue_type.value,
                    name=queue_data["name"],
                    description=queue_data["description"],
                    display_order=queue_data["display_order"],
                )
                session.add(queue)
                await session.flush()
                queues[queue_type] = queue
                print(f"  + Created: {queue_data['name']}")
        
        # ====================================================================
        # 3. Create/update spatial markers
        # ====================================================================
        print("\nMain Queue Markers:")
        main_queue = queues[QueueType.MAIN]
        await seed_markers(session, berghain.id, main_queue.id, MAIN_QUEUE_MARKERS)
        
        print("\nGuestlist Queue Markers:")
        gl_queue = queues[QueueType.GUESTLIST]
        await seed_markers(session, berghain.id, gl_queue.id, GL_QUEUE_MARKERS)
        
        # Re-entry queue uses same markers as GL
        print("\n(Re-entry queue shares GL markers)")
        
        await session.commit()
        print("\n✓ Seed data complete!")


async def seed_markers(
    session,
    club_id: uuid.UUID,
    queue_id: uuid.UUID,
    markers: list[dict],
) -> None:
    """Seed or update spatial markers for a queue."""
    for marker_data in markers:
        result = await session.execute(
            select(SpatialMarker).where(
                SpatialMarker.club_id == club_id,
                SpatialMarker.name == marker_data["name"],
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update queue_id if not set
            if existing.queue_id is None:
                existing.queue_id = queue_id
                print(f"  ~ Updated queue_id: {marker_data['name']}")
            else:
                print(f"  ✓ {marker_data['name']} exists")
        else:
            marker = SpatialMarker(
                id=uuid.uuid4(),
                club_id=club_id,
                queue_id=queue_id,
                **marker_data,
            )
            session.add(marker)
            print(f"  + Created: {marker_data['name']}")


async def main():
    """Main entry point."""
    print("=" * 50)
    print("Seeding KlubFlow Database")
    print("=" * 50)
    
    print("\nInitializing database...")
    await init_db()
    
    print("\nSeeding Berghain data...")
    await seed_berghain()


if __name__ == "__main__":
    asyncio.run(main())

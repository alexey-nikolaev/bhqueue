"""
BHQueue API - Main FastAPI application.

Tracks queue status at Berghain and other Berlin clubs.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db

settings = get_settings()

# Global reference to Telegram monitor task
_telegram_task: Optional[asyncio.Task] = None


async def _start_telegram_monitor():
    """Start the Telegram monitor in background."""
    from app.services.telegram_monitor import TelegramMonitor
    from app.database import async_session_maker
    from app.models.parsed_update import ParsedUpdate
    from app.models.club import Club
    from sqlalchemy import select
    
    monitor = TelegramMonitor()
    connected = await monitor.connect()
    
    if not connected:
        print("Telegram monitor: Failed to connect (check credentials)", flush=True)
        return
    
    print("Telegram monitor: Connected successfully", flush=True)
    
    async def on_message(data: dict):
        """Callback for new queue-related messages."""
        async with async_session_maker() as db:
            try:
                # Get Berghain club
                result = await db.execute(
                    select(Club).where(Club.slug == "berghain")
                )
                club = result.scalar_one_or_none()
                if not club:
                    print("Telegram monitor: Berghain club not found in DB", flush=True)
                    return
                
                # Check for duplicate
                existing = await db.execute(
                    select(ParsedUpdate).where(
                        ParsedUpdate.source == data["source"],
                        ParsedUpdate.source_id == data["source_id"],
                    )
                )
                if existing.scalar_one_or_none():
                    return  # Already recorded
                
                # Create parsed update
                parsed_update = ParsedUpdate(
                    club_id=club.id,
                    source=data["source"],
                    source_id=data["source_id"],
                    raw_text=data["raw_text"],
                    parsed_wait_minutes=data.get("parsed_wait_minutes"),
                    parsed_queue_length=data.get("parsed_queue_length"),
                    parsed_spatial_marker=data.get("parsed_spatial_marker"),
                    confidence=data.get("confidence", 0.5),
                    source_timestamp=data.get("source_timestamp"),
                )
                
                db.add(parsed_update)
                await db.commit()
                
                print(f"Telegram monitor: Saved update - {data.get('parsed_spatial_marker', 'unknown location')}, "
                      f"wait: {data.get('parsed_wait_minutes', '?')} min", flush=True)
                
            except Exception as e:
                print(f"Telegram monitor: Error saving update: {e}", flush=True)
    
    try:
        await monitor.listen_for_updates(on_message)
    except asyncio.CancelledError:
        print("Telegram monitor: Stopping...", flush=True)
        await monitor.disconnect()
        raise
    except Exception as e:
        print(f"Telegram monitor: Error: {e}", flush=True)
        await monitor.disconnect()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Runs on startup and shutdown.
    """
    global _telegram_task
    
    # Startup
    print(f"Starting {settings.app_name} in {settings.app_env} mode...", flush=True)
    await init_db()
    print("Database initialized.", flush=True)
    
    # Start Telegram monitor if enabled and credentials are configured
    if settings.enable_telegram_monitoring:
        if settings.telegram_api_id and settings.telegram_api_hash:
            print("Starting Telegram monitor...", flush=True)
            _telegram_task = asyncio.create_task(_start_telegram_monitor())
        else:
            print("Telegram monitor: Skipped (credentials not configured)", flush=True)
    else:
        print("Telegram monitor: Disabled by config", flush=True)
    
    yield
    
    # Shutdown
    print("Shutting down...", flush=True)
    
    # Stop Telegram monitor
    if _telegram_task and not _telegram_task.done():
        print("Stopping Telegram monitor...", flush=True)
        _telegram_task.cancel()
        try:
            await _telegram_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title=settings.app_name,
    description="Real-time queue tracking for Berlin nightclubs",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS middleware - allow frontend apps to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local web dev
        "http://localhost:8081",  # Expo web
        "http://localhost:19006",  # Expo web alt
        # Add production URLs here
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint - basic health check."""
    return {
        "app": settings.app_name,
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy"}


# Routers
from app.routers import auth, clubs, queue, admin

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(clubs.router, prefix="/api/clubs", tags=["Clubs"])
app.include_router(queue.router, prefix="/api/queue", tags=["Queue"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])

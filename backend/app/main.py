"""
BHQueue API - Main FastAPI application.

Tracks queue status at Berghain and other Berlin clubs.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Runs on startup and shutdown.
    """
    # Startup
    print(f"Starting {settings.app_name} in {settings.app_env} mode...")
    await init_db()
    print("Database initialized.")
    
    yield
    
    # Shutdown
    print("Shutting down...")


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
from app.routers import clubs

app.include_router(clubs.router, prefix="/api/clubs", tags=["Clubs"])

# Future routers:
# from app.routers import auth, queue
# app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
# app.include_router(queue.router, prefix="/api/queue", tags=["Queue"])

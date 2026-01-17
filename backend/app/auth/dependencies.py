"""
Authentication dependencies for FastAPI.
"""

from typing import Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_access_token
from app.config import get_settings
from app.database import get_db
from app.models import User

# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Get the current user if authenticated, None otherwise.
    
    Use this for endpoints that work with or without authentication.
    """
    if credentials is None:
        return None
    
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        return None
    
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    )
    return result.scalar_one_or_none()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Get the current authenticated user.
    
    Raises 401 if not authenticated or token is invalid.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if credentials is None:
        raise credentials_exception
    
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise credentials_exception
    
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    return user


async def verify_admin_access(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_admin_api_key: Optional[str] = Header(None, alias="X-Admin-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Verify admin access via either:
    1. Authenticated user with is_admin=True
    2. Valid X-Admin-API-Key header
    
    Returns the admin user if authenticated via JWT, None if via API key.
    Raises 403 if neither method succeeds.
    """
    settings = get_settings()
    
    # Method 1: Check API key
    if x_admin_api_key:
        if settings.admin_api_key and x_admin_api_key == settings.admin_api_key:
            return None  # Valid API key, no user context
        # Invalid API key - don't fall through, reject immediately
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin API key",
        )
    
    # Method 2: Check authenticated admin user
    if credentials:
        user_id = decode_access_token(credentials.credentials)
        if user_id:
            result = await db.execute(
                select(User).where(
                    User.id == user_id,
                    User.is_active == True,
                    User.is_admin == True,
                )
            )
            user = result.scalar_one_or_none()
            if user:
                return user
    
    # Neither method succeeded
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access required. Provide valid admin credentials or X-Admin-API-Key header.",
    )

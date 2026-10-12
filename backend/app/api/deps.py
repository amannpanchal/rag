"""FastAPI dependencies."""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.config import get_settings
from app.db.user_models import User
from app.services.auth_service import AuthService

_auth_service = AuthService()


def get_auth_service() -> AuthService:
    return _auth_service


async def get_current_user(request: Request) -> User:
    settings = get_settings()
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    user = await get_auth_service().resolve_session(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user

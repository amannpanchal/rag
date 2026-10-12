"""Authentication endpoints."""

from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import get_auth_service, get_current_user
from app.config import get_settings
from app.core.cookies import clear_session_cookie, set_session_cookie
from app.db.user_models import User
from app.schemas.auth import LoginRequest, UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("", response_model=UserResponse)
@router.post("/login", response_model=UserResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    auth: AuthService = Depends(get_auth_service),
) -> UserResponse:
    client = request.client.host if request.client else "unknown"
    user, token = await auth.login_or_register(body.email, body.password, client)
    set_session_cookie(response, token)
    return UserResponse.model_validate(user)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    auth: AuthService = Depends(get_auth_service),
) -> None:
    settings = get_settings()
    await auth.logout(request.cookies.get(settings.SESSION_COOKIE_NAME))
    clear_session_cookie(response)


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(user)

"""Authentication and session lifecycle."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import RateLimitError, UnauthorizedError
from app.core.passwords import hash_password, verify_password
from app.core.rate_limit import get_login_limiter
from app.db.user_models import User
from app.repositories.user_repository import SessionRepository, UserRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)

INVALID_CREDENTIALS = "Invalid email or password"


class AuthService:
    def __init__(
        self,
        users: UserRepository | None = None,
        sessions: SessionRepository | None = None,
    ) -> None:
        self.users = users or UserRepository()
        self.sessions = sessions or SessionRepository()

    async def login_or_register(self, email: str, password: str, client_key: str) -> tuple[User, str]:
        limiter = get_login_limiter()
        normalized_email = email.strip().lower()
        rate_key = f"{client_key}:{normalized_email}"
        if not limiter.allow(rate_key):
            raise RateLimitError()

        existing = await self.users.get_by_email(normalized_email)
        if existing is None:
            try:
                user = await self.users.create(email=normalized_email, password_hash=hash_password(password))
            except IntegrityError as exc:
                existing = await self.users.get_by_email(normalized_email)
                if existing is None or not verify_password(password, existing.password_hash):
                    raise UnauthorizedError(INVALID_CREDENTIALS) from exc
                user = existing
            token = await self.sessions.create(user.id)
            limiter.reset(rate_key)
            logger.info("Created user id=%s", user.id)
            return user, token

        if not verify_password(password, existing.password_hash):
            raise UnauthorizedError(INVALID_CREDENTIALS)

        token = await self.sessions.create(existing.id)
        limiter.reset(rate_key)
        logger.info("Authenticated user id=%s", existing.id)
        return existing, token

    async def logout(self, raw_token: str | None) -> None:
        if raw_token:
            await self.sessions.delete_by_token(raw_token)

    async def resolve_session(self, raw_token: str | None) -> User | None:
        if not raw_token:
            return None
        return await self.sessions.resolve_user(raw_token)

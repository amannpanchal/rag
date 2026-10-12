"""User and session persistence."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.config import get_settings
from app.db.postgres import get_db_session
from app.db.user_models import Session, User


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class UserRepository:
    async def get_by_email(self, email: str) -> User | None:
        async with get_db_session() as session:
            result = await session.execute(select(User).where(User.email == email.lower()))
            return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        async with get_db_session() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            return result.scalar_one_or_none()

    async def create(self, email: str, password_hash: str) -> User:
        async with get_db_session() as session:
            user = User(
                id=uuid.uuid4(),
                email=email.lower(),
                password_hash=password_hash,
            )
            session.add(user)
            await session.flush()
            await session.refresh(user)
            return user


class SessionRepository:
    async def create(self, user_id: uuid.UUID) -> str:
        settings = get_settings()
        raw = secrets.token_urlsafe(32)
        expires = datetime.now(tz=timezone.utc) + timedelta(seconds=settings.SESSION_TTL_SECONDS)
        async with get_db_session() as session:
            session.add(
                Session(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    token_hash=hash_session_token(raw),
                    expires_at=expires,
                )
            )
        return raw

    async def resolve_user(self, raw_token: str) -> User | None:
        token_hash = hash_session_token(raw_token)
        now = datetime.now(tz=timezone.utc)
        async with get_db_session() as session:
            result = await session.execute(
                select(Session).where(
                    Session.token_hash == token_hash,
                    Session.expires_at > now,
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            user_result = await session.execute(select(User).where(User.id == row.user_id))
            return user_result.scalar_one_or_none()

    async def delete_by_token(self, raw_token: str) -> None:
        async with get_db_session() as session:
            await session.execute(
                delete(Session).where(Session.token_hash == hash_session_token(raw_token))
            )

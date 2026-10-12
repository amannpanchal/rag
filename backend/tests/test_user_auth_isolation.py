"""Focused regression tests for authentication and vector tenant isolation."""

import uuid
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.core.passwords import verify_password
from sqlalchemy.exc import IntegrityError

from app.db.user_models import User
from app.services.auth_service import AuthService, INVALID_CREDENTIALS
from app.services.retrieval_service import retrieve_chunks


class FakeLimiter:
    def allow(self, _key: str) -> bool:
        return True

    def reset(self, _key: str) -> None:
        pass


class FakeUsers:
    def __init__(self) -> None:
        self.users: dict[str, User] = {}
        self.race_once = False

    async def get_by_email(self, email: str) -> User | None:
        return self.users.get(email)

    async def create(self, email: str, password_hash: str) -> User:
        user = User(id=uuid.uuid4(), email=email, password_hash=password_hash)
        self.users[email] = user
        if self.race_once:
            self.race_once = False
            raise IntegrityError("insert", {}, RuntimeError("unique constraint"))
        return user


class FakeSessions:
    async def create(self, user_id: uuid.UUID) -> str:
        return f"opaque-session-for-{user_id}"


class AuthenticationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.users = FakeUsers()
        self.service = AuthService(self.users, FakeSessions())
        self.limiter = patch("app.services.auth_service.get_login_limiter", return_value=FakeLimiter())
        self.limiter.start()
        self.addCleanup(self.limiter.stop)

    async def test_new_account_hashes_password_and_returns_session(self) -> None:
        user, token = await self.service.login_or_register("Person@Example.com", "strong-password", "test-new")
        self.assertEqual(user.email, "person@example.com")
        self.assertNotEqual(user.password_hash, "strong-password")
        self.assertTrue(verify_password("strong-password", user.password_hash))
        self.assertTrue(token.startswith("opaque-session-for-"))

    async def test_existing_password_authentication_and_rejection(self) -> None:
        user, _ = await self.service.login_or_register("person@example.com", "strong-password", "test-existing")
        same_user, _ = await self.service.login_or_register("PERSON@example.com", "strong-password", "test-existing")
        self.assertEqual(user.id, same_user.id)
        with self.assertRaisesRegex(Exception, INVALID_CREDENTIALS):
            await self.service.login_or_register("person@example.com", "wrong-password", "test-existing")
        self.assertEqual(len(self.users.users), 1)

    async def test_concurrent_unique_constraint_race_reuses_existing_account(self) -> None:
        self.users.race_once = True
        user, _ = await self.service.login_or_register("person@example.com", "strong-password", "test-race")
        self.assertEqual(user.email, "person@example.com")
        self.assertEqual(len(self.users.users), 1)


class RetrievalIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def test_qdrant_search_always_filters_by_server_user_id(self) -> None:
        client = SimpleNamespace(query_points=AsyncMock(return_value=SimpleNamespace(points=[])))
        settings = SimpleNamespace(QDRANT_COLLECTION="documents", RETRIEVAL_MIN_SCORE=0.6, RETRIEVAL_MAX_GAP=0.1)
        with (
            patch("app.services.retrieval_service.get_qdrant_client", return_value=client),
            patch("app.services.retrieval_service.get_settings", return_value=settings),
            patch("app.services.retrieval_service.embed_batch_with_retry", new=AsyncMock(return_value=[[0.1, 0.2]])),
        ):
            await retrieve_chunks("question", user_id="user-123", top_k=5)
        filters = client.query_points.await_args.kwargs["query_filter"].must
        self.assertEqual(filters[0].key, "user_id")
        self.assertEqual(filters[0].match.value, "user-123")


if __name__ == "__main__":
    unittest.main()


class FakeDbSession:
    def __init__(self, result: object) -> None:
        self.result = result
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return self.result


class DocumentOwnershipTests(unittest.IsolatedAsyncioTestCase):
    async def test_document_listing_query_is_scoped_to_authenticated_user(self) -> None:
        from contextlib import asynccontextmanager
        from app.services.document_query_service import list_documents

        user_id = uuid.uuid4()
        result = SimpleNamespace(scalar_one=lambda: 0, scalars=lambda: SimpleNamespace(all=lambda: []))
        session = FakeDbSession(result)

        @asynccontextmanager
        async def fake_db_session():
            yield session

        with patch("app.services.document_query_service.get_db_session", fake_db_session):
            response = await list_documents(user_id=user_id)
        self.assertEqual(response.total, 0)
        self.assertEqual(len(session.statements), 2)
        for statement in session.statements:
            self.assertIn("documents.user_id", str(statement))
            self.assertIn(user_id, statement.compile().params.values())

    async def test_delete_of_non_owned_document_stops_before_vector_delete(self) -> None:
        from contextlib import asynccontextmanager
        from app.services.document_query_service import delete_document

        session = FakeDbSession(SimpleNamespace(scalar_one_or_none=lambda: None))

        @asynccontextmanager
        async def fake_db_session():
            yield session

        with patch("app.services.document_query_service.get_db_session", fake_db_session):
            with self.assertRaisesRegex(KeyError, "not found"):
                await delete_document(uuid.uuid4(), uuid.uuid4())
        self.assertIn("documents.user_id", str(session.statements[0]))


class SessionLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_logout_revokes_the_cookie_session(self) -> None:
        class RevocableSessions(FakeSessions):
            def __init__(self) -> None:
                self.revoked: list[str] = []

            async def delete_by_token(self, token: str) -> None:
                self.revoked.append(token)

        sessions = RevocableSessions()
        service = AuthService(FakeUsers(), sessions)
        await service.logout("raw-cookie-session")
        self.assertEqual(sessions.revoked, ["raw-cookie-session"])

    async def test_expired_or_missing_session_is_not_resolved(self) -> None:
        from contextlib import asynccontextmanager
        from app.repositories.user_repository import SessionRepository

        session = FakeDbSession(SimpleNamespace(scalar_one_or_none=lambda: None))

        @asynccontextmanager
        async def fake_db_session():
            yield session

        with patch("app.repositories.user_repository.get_db_session", fake_db_session):
            self.assertIsNone(await SessionRepository().resolve_user("expired-cookie"))
        sql = str(session.statements[0])
        self.assertIn("sessions.expires_at", sql)
        self.assertIn(">", sql)

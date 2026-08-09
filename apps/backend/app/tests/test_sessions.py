"""Integration tests for the generic active-sessions endpoints
(GET/DELETE /api/v1/auth/sessions) — works across all user types."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.enums import UserType
from app.models.user import User
from app.models.user_token import UserToken


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def session_ctx():
    async with AsyncSessionLocal() as session:
        suffix = uuid.uuid4().hex[:10]
        user = User(
            id=uuid.uuid4(),
            email=f"sessions-{suffix}@test.local",
            password_hash="x",
            full_name="Sessions User",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        other_user = User(
            id=uuid.uuid4(),
            email=f"sessions-other-{suffix}@test.local",
            password_hash="x",
            full_name="Other User",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        session.add_all([user, other_user])
        await session.flush()

        now = datetime.now(UTC)
        token_a = UserToken(
            user_id=user.id,
            token_hash=f"hash-a-{suffix}",
            token_family=uuid.uuid4(),
            token_type="refresh",
            expires_at=now + timedelta(days=30),
            ip_address="127.0.0.1",
            user_agent="pytest-agent-a",
        )
        token_b = UserToken(
            user_id=user.id,
            token_hash=f"hash-b-{suffix}",
            token_family=uuid.uuid4(),
            token_type="refresh",
            expires_at=now + timedelta(days=30),
            ip_address="127.0.0.2",
            user_agent="pytest-agent-b",
        )
        expired_token = UserToken(
            user_id=user.id,
            token_hash=f"hash-expired-{suffix}",
            token_family=uuid.uuid4(),
            token_type="refresh",
            expires_at=now - timedelta(days=1),
        )
        other_token = UserToken(
            user_id=other_user.id,
            token_hash=f"hash-other-{suffix}",
            token_family=uuid.uuid4(),
            token_type="refresh",
            expires_at=now + timedelta(days=30),
        )
        session.add_all([token_a, token_b, expired_token, other_token])
        await session.commit()

        access_token = create_access_token(
            str(user.id), extra_claims={"user_type": UserType.AGENCY_USER.value}
        )

        yield {
            "user_id": user.id,
            "other_user_id": other_user.id,
            "access_token": access_token,
            "token_a_id": token_a.id,
            "token_b_id": token_b.id,
            "other_token_id": other_token.id,
        }

        for uid in (user.id, other_user.id):
            u = await session.get(User, uid)
            if u is not None:
                await session.delete(u)
        await session.commit()


class TestListSessions:
    async def test_lists_only_active_own_sessions(
        self, client: AsyncClient, session_ctx: dict
    ) -> None:
        resp = await client.get(
            "/api/v1/auth/sessions", headers=_headers(session_ctx["access_token"])
        )
        assert resp.status_code == 200
        ids = {s["id"] for s in resp.json()}
        assert str(session_ctx["token_a_id"]) in ids
        assert str(session_ctx["token_b_id"]) in ids
        assert str(session_ctx["other_token_id"]) not in ids
        assert len(resp.json()) == 2  # expired one excluded

    async def test_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/auth/sessions")
        assert resp.status_code == 401


class TestRevokeSession:
    async def test_revoke_own_session_succeeds(
        self, client: AsyncClient, session_ctx: dict
    ) -> None:
        resp = await client.delete(
            f"/api/v1/auth/sessions/{session_ctx['token_a_id']}",
            headers=_headers(session_ctx["access_token"]),
        )
        assert resp.status_code == 204

        listed = await client.get(
            "/api/v1/auth/sessions", headers=_headers(session_ctx["access_token"])
        )
        ids = {s["id"] for s in listed.json()}
        assert str(session_ctx["token_a_id"]) not in ids

    async def test_cannot_revoke_other_users_session(
        self, client: AsyncClient, session_ctx: dict
    ) -> None:
        resp = await client.delete(
            f"/api/v1/auth/sessions/{session_ctx['other_token_id']}",
            headers=_headers(session_ctx["access_token"]),
        )
        assert resp.status_code == 404

    async def test_revoke_nonexistent_session_returns_404(
        self, client: AsyncClient, session_ctx: dict
    ) -> None:
        resp = await client.delete(
            f"/api/v1/auth/sessions/{uuid.uuid4()}",
            headers=_headers(session_ctx["access_token"]),
        )
        assert resp.status_code == 404


class TestRevokeAllSessions:
    async def test_revoke_all_clears_every_session(
        self, client: AsyncClient, session_ctx: dict
    ) -> None:
        resp = await client.post(
            "/api/v1/auth/sessions/revoke-all", headers=_headers(session_ctx["access_token"])
        )
        assert resp.status_code == 200

        listed = await client.get(
            "/api/v1/auth/sessions", headers=_headers(session_ctx["access_token"])
        )
        assert listed.json() == []

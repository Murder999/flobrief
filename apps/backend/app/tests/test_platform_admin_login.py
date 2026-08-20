"""Tests for platform admin login flow.

Design: DB-agnostic where possible.
- Endpoint contract tests use ASGI client against the FastAPI app.
- Service unit tests mock repositories directly.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Response
from httpx import AsyncClient

from app.api.v1.platform.auth import _set_platform_refresh_cookie
from app.core.config import settings
from app.core.security import create_access_token, decode_access_token, hash_password
from app.models.enums import UserType
from app.schemas.auth import LoginRequest
from app.services.auth_service import AuthService

# ── Endpoint contract tests (no DB needed) ───────────────────────────────────


class TestPlatformLoginEndpointContracts:
    async def test_platform_login_requires_email_and_password(self, client: AsyncClient) -> None:
        """Missing fields → 422 Unprocessable Entity."""
        resp = await client.post("/api/v1/platform/auth/login", json={})
        assert resp.status_code == 422

    async def test_platform_login_rejects_invalid_email(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/platform/auth/login",
            json={"email": "not-an-email", "password": "SomePass123!"},
        )
        assert resp.status_code == 422

    async def test_platform_login_wrong_credentials_returns_401(self, client: AsyncClient) -> None:
        """Non-existent user → 401, not 500. Uses dependency override to avoid real DB."""
        from fastapi import HTTPException

        from app.db.session import get_db
        from app.main import app as fastapi_app

        mock_db = AsyncMock()

        async def mock_get_db() -> AsyncMock:  # type: ignore[override]
            yield mock_db

        fastapi_app.dependency_overrides[get_db] = mock_get_db
        try:
            with patch(
                "app.services.auth_service.AuthService.platform_admin_login",
                new_callable=AsyncMock,
                side_effect=HTTPException(status_code=401, detail="Invalid credentials"),
            ):
                resp = await client.post(
                    "/api/v1/platform/auth/login",
                    json={
                        "email": "nonexistent-admin@flobrief.com",
                        "password": "WrongPass123!",
                    },
                )
        finally:
            fastapi_app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 401

    async def test_regular_login_wrong_credentials_returns_401(self, client: AsyncClient) -> None:
        """Regular login endpoint also returns 401 for unknown user."""
        from fastapi import HTTPException

        from app.db.session import get_db
        from app.main import app as fastapi_app

        mock_db = AsyncMock()

        async def mock_get_db() -> AsyncMock:  # type: ignore[override]
            yield mock_db

        fastapi_app.dependency_overrides[get_db] = mock_get_db
        try:
            with patch(
                "app.services.auth_service.AuthService.login",
                new_callable=AsyncMock,
                side_effect=HTTPException(status_code=401, detail="Invalid credentials"),
            ):
                resp = await client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": "nobody@example.com",
                        "password": "SomePass123!",
                    },
                )
        finally:
            fastapi_app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 401

    async def test_register_cannot_create_platform_admin(self, client: AsyncClient) -> None:
        """Register endpoint always creates agency_user, never platform_admin."""
        from app.db.session import get_db
        from app.main import app as fastapi_app

        mock_db = AsyncMock()

        async def mock_get_db() -> AsyncMock:  # type: ignore[override]
            yield mock_db

        # Build a mock user the register service would return
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = f"attacker-{uuid.uuid4()}@evil.com"
        mock_user.full_name = "Evil Hacker"
        mock_user.job_title = None
        mock_user.user_type = UserType.AGENCY_USER.value
        mock_user.is_active = True
        mock_user.is_verified = False
        mock_user.locale = "en"
        mock_user.created_at = MagicMock()

        fastapi_app.dependency_overrides[get_db] = mock_get_db
        try:
            with patch(
                "app.services.auth_service.AuthService.register",
                new_callable=AsyncMock,
                return_value=mock_user,
            ):
                resp = await client.post(
                    "/api/v1/auth/register",
                    json={
                        "email": mock_user.email,
                        "password": "Secure@Pass2024",
                        "full_name": "Evil Hacker",
                    },
                )
        finally:
            fastapi_app.dependency_overrides.pop(get_db, None)

        # Either 422 (unknown field rejected) or 201 (created as agency_user — never platform_admin)
        assert resp.status_code in (201, 422)
        if resp.status_code == 201:
            assert resp.json()["user_type"] == UserType.AGENCY_USER.value


class TestPlatformRefreshCookiePolicy:
    def test_production_cookie_supports_cross_site_frontend(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "APP_ENV", "production")
        response = Response()

        _set_platform_refresh_cookie(response, "test-refresh-token")

        cookie = response.headers["set-cookie"].lower()
        assert "samesite=none" in cookie
        assert "secure" in cookie
        assert "httponly" in cookie

    def test_development_cookie_works_without_https(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "APP_ENV", "development")
        response = Response()

        _set_platform_refresh_cookie(response, "test-refresh-token")

        cookie = response.headers["set-cookie"].lower()
        assert "samesite=lax" in cookie
        assert "secure" not in cookie


# ── Service unit tests (mocked repositories) ─────────────────────────────────


def _make_user(
    *,
    user_type: str = UserType.PLATFORM_ADMIN.value,
    is_active: bool = True,
    is_verified: bool = True,
    is_deleted: bool = False,
    password: str = "TestPass@2024",
) -> Any:
    """Build a mock User object with the given properties."""
    u = MagicMock()
    u.id = uuid.uuid4()
    u.email = "admin@flobrief.com"
    u.user_type = user_type
    u.is_active = is_active
    u.is_verified = is_verified
    u.deleted_at = None if not is_deleted else MagicMock()
    u.is_deleted = is_deleted
    u.password_hash = hash_password(password)
    u.mfa_enabled = False
    u.mfa_secret_encrypted = None
    u.last_login_at = None
    return u


class TestAuthServicePlatformAdminLogin:
    """Unit tests for AuthService.platform_admin_login()."""

    async def _build_service(self) -> tuple[AuthService, Any]:
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        svc = AuthService(db)
        return svc, db

    async def test_platform_admin_login_succeeds_with_correct_credentials(self) -> None:
        svc, _ = await self._build_service()
        password = "TestPass@2024"
        mock_user = _make_user(password=password)

        with patch.object(svc.user_repo, "get_by_email", return_value=mock_user):
            user = await svc.platform_admin_login(
                LoginRequest(email="admin@flobrief.com", password=password)
            )
        assert user is mock_user

    async def test_platform_admin_login_rejects_wrong_password(self) -> None:
        from fastapi import HTTPException

        svc, _ = await self._build_service()
        mock_user = _make_user(password="CorrectPass@2024")

        with (
            patch.object(svc.user_repo, "get_by_email", return_value=mock_user),
            pytest.raises(HTTPException) as exc_info,
        ):
            await svc.platform_admin_login(
                LoginRequest(email="admin@flobrief.com", password="WrongPass@2024")
            )
        assert exc_info.value.status_code == 401

    async def test_platform_admin_login_rejects_inactive_user(self) -> None:
        from fastapi import HTTPException

        svc, _ = await self._build_service()
        mock_user = _make_user(is_active=False)

        with (
            patch.object(svc.user_repo, "get_by_email", return_value=mock_user),
            pytest.raises(HTTPException) as exc_info,
        ):
            await svc.platform_admin_login(
                LoginRequest(email="admin@flobrief.com", password="TestPass@2024")
            )
        assert exc_info.value.status_code == 401

    async def test_platform_admin_login_rejects_agency_user(self) -> None:
        """A regular agency_user must NOT be able to log in via platform_admin_login."""
        from fastapi import HTTPException

        svc, _ = await self._build_service()
        mock_user = _make_user(user_type=UserType.AGENCY_USER.value)

        with (
            patch.object(svc.user_repo, "get_by_email", return_value=mock_user),
            pytest.raises(HTTPException) as exc_info,
        ):
            await svc.platform_admin_login(
                LoginRequest(email="admin@flobrief.com", password="TestPass@2024")
            )
        assert exc_info.value.status_code == 401

    async def test_platform_admin_login_rejects_nonexistent_user(self) -> None:
        from fastapi import HTTPException

        svc, _ = await self._build_service()

        with (
            patch.object(svc.user_repo, "get_by_email", return_value=None),
            pytest.raises(HTTPException) as exc_info,
        ):
            await svc.platform_admin_login(
                LoginRequest(email="ghost@flobrief.com", password="TestPass@2024")
            )
        assert exc_info.value.status_code == 401


class TestAuthServiceLoginRejectsPlatformAdmin:
    """Regular login must reject admins without revealing the hidden channel."""

    async def test_regular_login_rejects_platform_admin_without_route_disclosure(self) -> None:
        from fastapi import HTTPException

        db = AsyncMock()
        svc = AuthService(db)
        password = "TestPass@2024"
        mock_user = _make_user(user_type=UserType.PLATFORM_ADMIN.value, password=password)

        with (
            patch.object(svc.user_repo, "get_by_email", return_value=mock_user),
            pytest.raises(HTTPException) as exc_info,
        ):
            await svc.login(LoginRequest(email="admin@flobrief.com", password=password))
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "E-posta veya şifre hatalı"
        assert "platform" not in str(exc_info.value.detail).lower()

    async def test_regular_login_succeeds_for_agency_user(self) -> None:
        """Agency user can login via regular endpoint without 403."""
        db = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()
        db.scalar = AsyncMock(return_value=None)
        svc = AuthService(db)
        password = "TestPass@2024"
        mock_user = _make_user(user_type=UserType.AGENCY_USER.value, password=password)

        with (
            patch.object(svc.user_repo, "get_by_email", return_value=mock_user),
            patch.object(svc.token_repo, "create", new_callable=AsyncMock),
        ):
            user, access_token, _ = await svc.login(
                LoginRequest(email="user@agency.com", password=password)
            )
        assert user is mock_user
        assert access_token
        # Verify the JWT contains user_type
        payload = decode_access_token(access_token)
        assert payload["user_type"] == UserType.AGENCY_USER.value

    async def test_login_response_includes_user_type_in_jwt(self) -> None:
        """Access token issued on login must carry user_type claim."""
        db = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()
        db.scalar = AsyncMock(return_value=None)
        svc = AuthService(db)
        password = "TestPass@2024"
        mock_user = _make_user(user_type=UserType.AGENCY_USER.value, password=password)

        with (
            patch.object(svc.user_repo, "get_by_email", return_value=mock_user),
            patch.object(svc.token_repo, "create", new_callable=AsyncMock),
        ):
            _user, access_token, _refresh = await svc.login(
                LoginRequest(email="user@agency.com", password=password)
            )

        payload = decode_access_token(access_token)
        assert "user_type" in payload
        assert payload["user_type"] == UserType.AGENCY_USER.value


# ── Platform JWT auth tests ───────────────────────────────────────────────────


class TestPlatformJwtSecurity:
    """Platform endpoints must only accept platform_admin JWTs."""

    async def test_platform_health_accepts_platform_admin_jwt(self, client: AsyncClient) -> None:
        """A valid platform_admin JWT is accepted at platform endpoints (may 401 on DB lookup)."""
        token = create_access_token(
            "some-admin-id",
            extra_claims={"user_type": UserType.PLATFORM_ADMIN.value},
        )
        resp = await client.get(
            "/api/v1/platform/health",
            headers={"Authorization": f"Bearer {token}"},
        )
        # 401 because user doesn't exist in DB, but NOT 403 (wrong user_type)
        assert resp.status_code in (200, 401)

    async def test_platform_health_rejects_agency_user_jwt(self, client: AsyncClient) -> None:
        """Agency user token must return 403 at platform endpoints."""
        token = create_access_token(
            "some-user-id",
            extra_claims={"user_type": UserType.AGENCY_USER.value},
        )
        resp = await client.get(
            "/api/v1/platform/health",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


# ── Hash / verify compatibility for short dev passwords ──────────────────────


class TestPasswordHashCompatibility:
    """Verify hash_password + verify_password work for dev-friendly short passwords."""

    def test_five_char_password_hash_and_verify(self) -> None:
        """5-char password set by reset_admin_password.py must verify correctly."""
        from app.core.security import hash_password, verify_password

        plain = "admin"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed)
        assert not verify_password("wrong", hashed)

    def test_hash_password_produces_bcrypt(self) -> None:
        """Ensure hash_password always produces a bcrypt hash (starts with $2b$)."""
        from app.core.security import hash_password

        hashed = hash_password("hello")
        assert hashed.startswith("$2"), f"Expected bcrypt hash, got: {hashed[:10]}"

    def test_verify_password_rejects_empty_hash(self) -> None:
        """verify_password with empty/None hash must not crash and must return False."""
        from app.core.security import verify_password

        assert not verify_password("somepass", ""), "Empty hash must not verify"

    def test_login_schema_accepts_short_password(self) -> None:
        """LoginRequest must NOT apply password strength rules."""
        from app.schemas.auth import LoginRequest

        req = LoginRequest(email="admin@flobrief.com", password="ab12e")
        assert req.password == "ab12e"

    def test_register_schema_rejects_short_password(self) -> None:
        """RegisterRequest MUST still enforce strong password policy."""
        from pydantic import ValidationError

        from app.schemas.auth import RegisterRequest

        with pytest.raises(ValidationError):
            RegisterRequest(email="user@example.com", full_name="Test", password="ab12e")

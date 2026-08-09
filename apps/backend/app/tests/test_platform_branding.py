"""Integration tests for platform-level white-label defaults and the
public branding fallback-merge (agency without white-label -> platform defaults).
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.agency import Agency
from app.models.enums import UserType
from app.models.platform_branding_defaults import PlatformBrandingDefaults
from app.models.user import User


def _admin_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def platform_admin_token():
    async with AsyncSessionLocal() as session:
        suffix = uuid.uuid4().hex[:10]
        admin = User(
            id=uuid.uuid4(),
            email=f"padmin-branding-{suffix}@test.local",
            password_hash="x",
            full_name="Fixture Admin",
            user_type=UserType.PLATFORM_ADMIN.value,
            is_active=True,
            is_verified=True,
        )
        session.add(admin)
        await session.commit()
        token = create_access_token(
            str(admin.id), extra_claims={"user_type": UserType.PLATFORM_ADMIN.value}
        )
        yield token
        # admin row intentionally left in place: platform_audit_logs.admin_user_id
        # is ON DELETE RESTRICT and audit rows are immutable once written.


@pytest.fixture(autouse=True)
async def _cleanup_platform_branding_defaults():
    yield
    async with AsyncSessionLocal() as session:
        from sqlalchemy import delete

        await session.execute(delete(PlatformBrandingDefaults))
        await session.commit()


class TestPlatformBrandingDefaults:
    async def test_get_creates_singleton_with_nulls(
        self, client: AsyncClient, platform_admin_token: str
    ) -> None:
        resp = await client.get(
            "/api/v1/platform/branding", headers=_admin_headers(platform_admin_token)
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["portal_name"] is None
        assert body["logo_url"] is None

    async def test_update_persists_fields(
        self, client: AsyncClient, platform_admin_token: str
    ) -> None:
        resp = await client.patch(
            "/api/v1/platform/branding",
            json={
                "portal_name": "Flobrief Studio",
                "primary_color": "#6366f1",
                "support_email": "destek@flobrief.com",
            },
            headers=_admin_headers(platform_admin_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["portal_name"] == "Flobrief Studio"
        assert body["primary_color"] == "#6366F1"
        assert body["support_email"] == "destek@flobrief.com"

    async def test_invalid_color_rejected(
        self, client: AsyncClient, platform_admin_token: str
    ) -> None:
        resp = await client.patch(
            "/api/v1/platform/branding",
            json={"primary_color": "not-a-color"},
            headers=_admin_headers(platform_admin_token),
        )
        assert resp.status_code == 422

    async def test_invalid_url_rejected(
        self, client: AsyncClient, platform_admin_token: str
    ) -> None:
        resp = await client.patch(
            "/api/v1/platform/branding",
            json={"terms_url": "not-a-url"},
            headers=_admin_headers(platform_admin_token),
        )
        assert resp.status_code == 422

    async def test_reset_clears_fields(
        self, client: AsyncClient, platform_admin_token: str
    ) -> None:
        await client.patch(
            "/api/v1/platform/branding",
            json={"portal_name": "Temp Name"},
            headers=_admin_headers(platform_admin_token),
        )
        resp = await client.post(
            "/api/v1/platform/branding/reset", headers=_admin_headers(platform_admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["portal_name"] is None

    async def test_non_admin_forbidden(self, client: AsyncClient) -> None:
        async with AsyncSessionLocal() as session:
            user = User(
                id=uuid.uuid4(),
                email=f"agencyuser-{uuid.uuid4().hex[:8]}@test.local",
                password_hash="x",
                full_name="Agency User",
                user_type=UserType.AGENCY_USER.value,
                is_active=True,
                is_verified=True,
            )
            session.add(user)
            await session.commit()
            token = create_access_token(
                str(user.id), extra_claims={"user_type": UserType.AGENCY_USER.value}
            )
        resp = await client.get("/api/v1/platform/branding", headers=_admin_headers(token))
        assert resp.status_code == 403

    async def test_public_defaults_endpoint_requires_no_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/public/branding/platform-defaults")
        assert resp.status_code == 200

    async def test_unconfigured_platform_logo_returns_404(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/public/branding/platform-logo")
        assert resp.status_code == 404


class TestPublicBrandingFallback:
    async def test_public_branding_falls_back_to_platform_defaults(
        self, client: AsyncClient, platform_admin_token: str
    ) -> None:
        """An agency with no white-label configured should surface platform
        defaults (portal name, colors, footer) instead of a bare/empty view."""
        await client.patch(
            "/api/v1/platform/branding",
            json={"portal_name": "Flobrief Platform Default", "primary_color": "#123456"},
            headers=_admin_headers(platform_admin_token),
        )

        from app.services.branding_service import BrandingService

        async with AsyncSessionLocal() as session:
            agency = Agency(
                id=uuid.uuid4(),
                name="Fallback Test Agency",
                slug=f"fallback-{uuid.uuid4().hex[:10]}",
            )
            session.add(agency)
            await session.commit()

            view = await BrandingService(session)._build_public_branding(agency.id)
            assert view.is_branded is False
            assert view.brand_name == "Flobrief Platform Default"
            assert view.primary_color == "#123456"

            await session.delete(agency)
            await session.commit()

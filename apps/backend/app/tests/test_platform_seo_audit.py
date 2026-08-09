"""Integration tests for the SEO audit engine, page inventory, health summary,
and the PageSpeed/GSC/GA4 setup-state endpoints (must never fake data)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.enums import UserType
from app.models.platform_seo_settings import PlatformGrowthSettings, PlatformSeoPageSettings
from app.models.user import User


def _admin_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def platform_admin_token():
    async with AsyncSessionLocal() as session:
        admin = User(
            id=uuid.uuid4(),
            email=f"padmin-seo-{uuid.uuid4().hex[:10]}@test.local",
            password_hash="x",
            full_name="Fixture Admin",
            user_type=UserType.PLATFORM_ADMIN.value,
            is_active=True,
            is_verified=True,
        )
        session.add(admin)
        await session.commit()
        yield create_access_token(
            str(admin.id), extra_claims={"user_type": UserType.PLATFORM_ADMIN.value}
        )


@pytest.fixture(autouse=True)
async def _cleanup_seo_settings():
    yield
    async with AsyncSessionLocal() as session:
        await session.execute(delete(PlatformSeoPageSettings))
        await session.execute(delete(PlatformGrowthSettings))
        await session.commit()


class TestSeoAudit:
    async def test_audit_flags_missing_home_metadata(
        self, client: AsyncClient, platform_admin_token: str
    ) -> None:
        resp = await client.get(
            "/api/v1/platform/seo/audit", headers=_admin_headers(platform_admin_token)
        )
        assert resp.status_code == 200
        issues = resp.json()
        assert any(i["page_key"] == "home" and i["severity"] == "high" for i in issues)
        assert any(i["area"] == "robots" for i in issues)

    async def test_audit_clears_after_filling_home_metadata(
        self, client: AsyncClient, platform_admin_token: str
    ) -> None:
        await client.patch(
            "/api/v1/platform/seo/pages/home",
            json={
                "title": "Flobrief — Brief Yönetimi",
                "description": "A" * 100,
                "canonical_url": "https://flobrief.com/",
                "og_title": "Flobrief",
                "og_image_url": "https://flobrief.com/og.png",
                "indexable": True,
            },
            headers=_admin_headers(platform_admin_token),
        )
        resp = await client.get(
            "/api/v1/platform/seo/audit", headers=_admin_headers(platform_admin_token)
        )
        issues = resp.json()
        home_issues = [i for i in issues if i["page_key"] == "home"]
        assert home_issues == []

    async def test_health_score_improves_after_fixes(
        self, client: AsyncClient, platform_admin_token: str
    ) -> None:
        before = await client.get(
            "/api/v1/platform/seo/health", headers=_admin_headers(platform_admin_token)
        )
        score_before = before.json()["health_score"]

        await client.patch(
            "/api/v1/platform/seo/pages/home",
            json={
                "title": "T",
                "description": "D" * 80,
                "canonical_url": "https://x.com/",
                "indexable": True,
            },
            headers=_admin_headers(platform_admin_token),
        )
        await client.patch(
            "/api/v1/platform/seo/tracking",
            json={"public_app_url": "https://flobrief.com"},
            headers=_admin_headers(platform_admin_token),
        )
        await client.patch(
            "/api/v1/platform/seo/robots",
            json={
                "robots_txt": "User-agent: *\nAllow: /\nSitemap: https://flobrief.com/sitemap.xml"
            },
            headers=_admin_headers(platform_admin_token),
        )

        after = await client.get(
            "/api/v1/platform/seo/health", headers=_admin_headers(platform_admin_token)
        )
        assert after.json()["health_score"] > score_before

    async def test_page_inventory_includes_not_built_pages(
        self, client: AsyncClient, platform_admin_token: str
    ) -> None:
        resp = await client.get(
            "/api/v1/platform/seo/pages/inventory", headers=_admin_headers(platform_admin_token)
        )
        items = resp.json()
        keys = {i["page_key"]: i for i in items}
        assert keys["home"]["status"] == "published"
        assert keys["about"]["status"] == "not_built"

    async def test_audit_requires_platform_admin(self, client: AsyncClient) -> None:
        async with AsyncSessionLocal() as session:
            user = User(
                id=uuid.uuid4(),
                email=f"nonadmin-{uuid.uuid4().hex[:8]}@test.local",
                password_hash="x",
                full_name="Non Admin",
                user_type=UserType.AGENCY_USER.value,
                is_active=True,
                is_verified=True,
            )
            session.add(user)
            await session.commit()
            token = create_access_token(
                str(user.id), extra_claims={"user_type": UserType.AGENCY_USER.value}
            )
        resp = await client.get("/api/v1/platform/seo/audit", headers=_admin_headers(token))
        assert resp.status_code == 403


class TestIntegrationSetupStates:
    async def test_pagespeed_without_key_returns_not_configured(
        self, client: AsyncClient, platform_admin_token: str
    ) -> None:
        resp = await client.get(
            "/api/v1/platform/seo/integrations/pagespeed",
            headers=_admin_headers(platform_admin_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["configured"] is False
        assert "PAGESPEED_API_KEY" in body["detail"]["required_env"]

    async def test_pagespeed_run_without_key_returns_409_not_fake_data(
        self, client: AsyncClient, platform_admin_token: str
    ) -> None:
        resp = await client.get(
            "/api/v1/platform/seo/pagespeed?url=https://flobrief.com",
            headers=_admin_headers(platform_admin_token),
        )
        assert resp.status_code == 409

    async def test_search_console_without_credentials_returns_not_configured(
        self, client: AsyncClient, platform_admin_token: str
    ) -> None:
        resp = await client.get(
            "/api/v1/platform/seo/integrations/search-console",
            headers=_admin_headers(platform_admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["configured"] is False

    async def test_ga4_without_credentials_returns_not_configured(
        self, client: AsyncClient, platform_admin_token: str
    ) -> None:
        resp = await client.get(
            "/api/v1/platform/seo/integrations/ga4",
            headers=_admin_headers(platform_admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["configured"] is False

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException, Request
from httpx import AsyncClient
from sqlalchemy import delete, func, select

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.brand import Brand
from app.models.brief import Brief
from app.models.brief_template import BriefTemplate
from app.models.calendar import CalendarItem
from app.models.demo_sandbox import DemoSandbox, PlatformDemoSettings
from app.models.enums import AgencyStatus, UserType
from app.models.subscription import Subscription
from app.models.user import User
from app.models.user_token import UserToken
from app.services.demo_access import enforce_demo_workspace_request, ensure_demo_user_access
from app.services.demo_sandbox_service import DemoSandboxService


@pytest.fixture(autouse=True)
async def _cleanup_demo_records():
    yield
    async with AsyncSessionLocal() as db:
        agency_ids = list(
            (await db.execute(select(Agency.id).where(Agency.is_demo.is_(True)))).scalars()
        )
        user_ids = list(
            (
                await db.execute(
                    select(DemoSandbox.owner_user_id).where(DemoSandbox.agency_id.in_(agency_ids))
                )
            ).scalars()
        )
        if agency_ids:
            await db.execute(delete(CalendarItem).where(CalendarItem.agency_id.in_(agency_ids)))
            await db.execute(delete(Brief).where(Brief.agency_id.in_(agency_ids)))
            await db.execute(delete(BriefTemplate).where(BriefTemplate.agency_id.in_(agency_ids)))
            await db.execute(delete(Brand).where(Brand.agency_id.in_(agency_ids)))
            await db.execute(delete(Subscription).where(Subscription.agency_id.in_(agency_ids)))
            await db.execute(delete(AgencyMember).where(AgencyMember.agency_id.in_(agency_ids)))
            await db.execute(delete(DemoSandbox).where(DemoSandbox.agency_id.in_(agency_ids)))
            await db.execute(delete(Agency).where(Agency.id.in_(agency_ids)))
        if user_ids:
            await db.execute(delete(UserToken).where(UserToken.user_id.in_(user_ids)))
            await db.execute(delete(User).where(User.id.in_(user_ids)))
        await db.execute(delete(PlatformDemoSettings))
        await db.commit()


async def _enable_demo(
    *,
    max_active: int = 5,
    max_per_ip: int = 2,
) -> None:
    async with AsyncSessionLocal() as db:
        db.add(
            PlatformDemoSettings(
                setting_key="default",
                enabled=True,
                duration_hours=4,
                max_active_sandboxes=max_active,
                max_creations_per_ip_per_day=max_per_ip,
                captcha_required=False,
            )
        )
        await db.commit()


async def test_public_demo_defaults_to_disabled(client: AsyncClient) -> None:
    response = await client.get("/api/v1/demo/status")
    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert response.json()["available"] is False


async def test_demo_creation_is_isolated_seeded_and_returns_session() -> None:
    await _enable_demo()
    async with AsyncSessionLocal() as db:
        sandbox, access_token, refresh_token = await DemoSandboxService(db).create(
            ip_address="203.0.113.10",
            user_agent="pytest",
            turnstile_token=None,
        )
        assert access_token
        assert refresh_token
        agency = await db.get(Agency, sandbox.agency_id)
        user = await db.get(User, sandbox.owner_user_id)
        assert agency is not None and agency.is_demo is True
        assert agency.demo_expires_at == sandbox.expires_at
        assert user is not None
        assert user.email.endswith("@sandbox.flobrief.invalid")

        brand_count = await db.scalar(
            select(func.count(Brand.id)).where(Brand.agency_id == sandbox.agency_id)
        )
        brief_count = await db.scalar(
            select(func.count(Brief.id)).where(Brief.agency_id == sandbox.agency_id)
        )
        calendar_count = await db.scalar(
            select(func.count(CalendarItem.id)).where(CalendarItem.agency_id == sandbox.agency_id)
        )
        assert (brand_count, brief_count, calendar_count) == (3, 5, 6)


async def test_demo_creation_enforces_durable_ip_quota() -> None:
    await _enable_demo(max_per_ip=1)
    async with AsyncSessionLocal() as db:
        service = DemoSandboxService(db)
        await service.create(
            ip_address="203.0.113.20",
            user_agent="pytest",
            turnstile_token=None,
        )
    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as exc_info:
            await DemoSandboxService(db).create(
                ip_address="203.0.113.20",
                user_agent="pytest",
                turnstile_token=None,
            )
        assert exc_info.value.status_code == 429


async def test_termination_revokes_access_and_suspends_tenant() -> None:
    await _enable_demo()
    async with AsyncSessionLocal() as db:
        sandbox, _, _ = await DemoSandboxService(db).create(
            ip_address="203.0.113.30",
            user_agent="pytest",
            turnstile_token=None,
        )
        await DemoSandboxService(db).terminate(sandbox, reason="platform_admin")
        await db.commit()

        agency = await db.get(Agency, sandbox.agency_id)
        user = await db.get(User, sandbox.owner_user_id)
        assert sandbox.status == "terminated"
        assert agency is not None and agency.status == AgencyStatus.SUSPENDED.value
        assert user is not None and user.is_active is False
        with pytest.raises(HTTPException) as exc_info:
            await ensure_demo_user_access(db, user.id)
        assert exc_info.value.status_code == 401


async def test_expired_demo_access_fails_without_waiting_for_scheduler() -> None:
    await _enable_demo()
    async with AsyncSessionLocal() as db:
        sandbox, _, _ = await DemoSandboxService(db).create(
            ip_address="203.0.113.40",
            user_agent="pytest",
            turnstile_token=None,
        )
        agency = await db.get(Agency, sandbox.agency_id)
        assert agency is not None
        agency.demo_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await db.commit()
        with pytest.raises(HTTPException) as exc_info:
            await ensure_demo_user_access(db, sandbox.owner_user_id)
        assert exc_info.value.status_code == 401


async def test_demo_blocks_external_mutations_but_allows_product_work() -> None:
    agency = Agency(
        name="Guard Demo",
        slug=f"guard-demo-{uuid.uuid4().hex}",
        status=AgencyStatus.ACTIVE.value,
        is_demo=True,
        demo_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    blocked_request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/billing/checkout",
            "raw_path": b"/api/v1/billing/checkout",
            "query_string": b"",
            "headers": [],
            "scheme": "https",
            "server": ("test", 443),
            "client": ("203.0.113.50", 1234),
        }
    )
    with pytest.raises(HTTPException) as exc_info:
        enforce_demo_workspace_request(agency, blocked_request)
    assert exc_info.value.status_code == 403

    allowed_request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/briefs",
            "raw_path": b"/api/v1/briefs",
            "query_string": b"",
            "headers": [],
            "scheme": "https",
            "server": ("test", 443),
            "client": ("203.0.113.50", 1234),
        }
    )
    enforce_demo_workspace_request(agency, allowed_request)


async def test_platform_admin_can_update_and_list_demo_settings(
    client: AsyncClient,
) -> None:
    async with AsyncSessionLocal() as db:
        admin = User(
            email=f"demo-admin-{uuid.uuid4().hex}@test.local",
            password_hash="x",
            full_name="Demo Admin",
            user_type=UserType.PLATFORM_ADMIN.value,
            is_active=True,
            is_verified=True,
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        admin_id = admin.id
    token = create_access_token(
        str(admin_id),
        extra_claims={"user_type": UserType.PLATFORM_ADMIN.value},
    )
    headers = {"Authorization": f"Bearer {token}"}

    update_response = await client.patch(
        "/api/v1/platform/demo/settings",
        json={
            "enabled": True,
            "captcha_required": False,
            "duration_hours": 6,
            "max_active_sandboxes": 12,
            "max_creations_per_ip_per_day": 3,
        },
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["enabled"] is True
    assert update_response.json()["duration_hours"] == 6

    list_response = await client.get("/api/v1/platform/demo/sandboxes", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json() == []


async def test_demo_tenants_are_excluded_from_commercial_admin_views(
    client: AsyncClient,
) -> None:
    await _enable_demo()
    async with AsyncSessionLocal() as db:
        admin = User(
            email=f"metrics-admin-{uuid.uuid4().hex}@test.local",
            password_hash="x",
            full_name="Metrics Admin",
            user_type=UserType.PLATFORM_ADMIN.value,
            is_active=True,
            is_verified=True,
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        admin_id = admin.id

    token = create_access_token(
        str(admin_id),
        extra_claims={"user_type": UserType.PLATFORM_ADMIN.value},
    )
    headers = {"Authorization": f"Bearer {token}"}
    before = await client.get("/api/v1/platform/dashboard", headers=headers)
    assert before.status_code == 200

    async with AsyncSessionLocal() as db:
        sandbox, _, _ = await DemoSandboxService(db).create(
            ip_address="203.0.113.60",
            user_agent="pytest",
            turnstile_token=None,
        )
        demo_agency_id = str(sandbox.agency_id)
        demo_user_id = str(sandbox.owner_user_id)

    after = await client.get("/api/v1/platform/dashboard", headers=headers)
    assert after.status_code == 200
    assert after.json() == before.json()

    agencies = await client.get("/api/v1/platform/agencies", headers=headers)
    brands = await client.get("/api/v1/platform/brands", headers=headers)
    users = await client.get("/api/v1/platform/users", headers=headers)
    assert agencies.status_code == brands.status_code == users.status_code == 200
    assert demo_agency_id not in {item["id"] for item in agencies.json()}
    assert all(item["agency_id"] != demo_agency_id for item in brands.json())
    assert demo_user_id not in {item["id"] for item in users.json()}

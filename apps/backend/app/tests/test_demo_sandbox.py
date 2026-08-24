from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException, Request
from httpx import AsyncClient
from sqlalchemy import delete, func, select

from app.core.security import create_access_token, decode_access_token
from app.db.session import AsyncSessionLocal
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.brand import Brand
from app.models.brand_member import BrandMember
from app.models.brief import Brief
from app.models.brief_template import BriefTemplate
from app.models.calendar import CalendarItem
from app.models.demo_sandbox import DemoSandbox, PlatformDemoSettings
from app.models.enums import (
    AgencyStatus,
    BrandMemberRole,
    BrandMemberStatus,
    UserType,
)
from app.models.invitation import Invitation
from app.models.subscription import Subscription
from app.models.user import User
from app.models.user_token import UserToken
from app.services.demo_access import enforce_demo_workspace_request, ensure_demo_user_access
from app.services.demo_sandbox_service import DemoSandboxService, terminate_expired_sandboxes
from app.services.token_service import (
    TOKEN_TYPE_REFRESH,
    generate_token,
    hash_token,
    new_token_family,
)


@pytest.fixture(autouse=True)
async def _cleanup_demo_records():
    yield
    async with AsyncSessionLocal() as db:
        agency_ids = list(
            (await db.execute(select(Agency.id).where(Agency.is_demo.is_(True)))).scalars()
        )
        identity_rows = (
            await db.execute(
                select(DemoSandbox.owner_user_id, DemoSandbox.brand_user_id).where(
                    DemoSandbox.agency_id.in_(agency_ids)
                )
            )
        ).all()
        user_ids = list(
            {
                user_id
                for owner_user_id, brand_user_id in identity_rows
                for user_id in (owner_user_id, brand_user_id)
                if user_id is not None
            }
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
        brand_user = await db.get(User, sandbox.brand_user_id)
        assert agency is not None and agency.is_demo is True
        assert agency.demo_expires_at == sandbox.expires_at
        assert user is not None
        assert user.email.endswith("@sandbox.flobrief.invalid")
        assert brand_user is not None
        assert brand_user.user_type == UserType.BRAND_USER.value
        assert brand_user.is_active is False

        membership = await db.scalar(
            select(BrandMember)
            .join(Brand, Brand.id == BrandMember.brand_id)
            .where(
                BrandMember.user_id == brand_user.id,
                Brand.agency_id == sandbox.agency_id,
            )
        )
        assert membership is not None
        assert membership.role == BrandMemberRole.BRAND_MANAGER.value
        assert membership.status == BrandMemberStatus.ACTIVE.value

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


async def test_demo_portal_switch_rotates_identity_both_ways(client: AsyncClient) -> None:
    await _enable_demo()
    async with AsyncSessionLocal() as db:
        sandbox, agency_access, _ = await DemoSandboxService(db).create(
            ip_address="203.0.113.11",
            user_agent="pytest",
            turnstile_token=None,
        )
        assert sandbox.brand_user_id is not None
        agency_user_id = sandbox.owner_user_id
        brand_user_id = sandbox.brand_user_id
        agency_id = sandbox.agency_id
        sandbox_expires_at = sandbox.expires_at

    agency_headers = {"Authorization": f"Bearer {agency_access}"}
    initial_agency_session_id = decode_access_token(agency_access)["demo_session_id"]
    agency_session = await client.get("/api/v1/demo/session", headers=agency_headers)
    assert agency_session.status_code == 200
    assert agency_session.json()["active_portal"] == "agency"

    to_brand = await client.post(
        "/api/v1/demo/switch-portal",
        json={"portal": "brand"},
        headers=agency_headers,
    )
    assert to_brand.status_code == 200
    brand_payload = to_brand.json()
    assert brand_payload["portal"] == "brand"
    assert brand_payload["redirect_to"] == "/brand/dashboard"
    assert client.cookies.get("refresh_token")
    brand_access = brand_payload["access_token"]
    brand_claims = decode_access_token(brand_access)
    assert brand_claims["sub"] == str(brand_user_id)
    assert brand_claims["user_type"] == UserType.BRAND_USER.value
    first_brand_session_id = brand_claims["demo_session_id"]
    assert first_brand_session_id != initial_agency_session_id
    assert brand_claims["exp"] <= int(sandbox_expires_at.timestamp())
    assert brand_payload["expires_in"] <= (
        int((sandbox_expires_at - datetime.now(UTC)).total_seconds()) + 2
    )

    stale_agency = await client.get("/api/v1/auth/me", headers=agency_headers)
    assert stale_agency.status_code == 401

    brand_headers = {"Authorization": f"Bearer {brand_access}"}
    brand_session = await client.get("/api/v1/demo/session", headers=brand_headers)
    assert brand_session.status_code == 200
    assert brand_session.json()["active_portal"] == "brand"
    brand_me = await client.get("/api/v1/brand-portal/me", headers=brand_headers)
    assert brand_me.status_code == 200
    assert brand_me.json()["user_id"] == str(brand_user_id)
    assert brand_me.json()["membership_role"] == BrandMemberRole.BRAND_MANAGER.value

    refreshed = await client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200
    refreshed_brand_access = refreshed.json()["access_token"]
    refreshed_brand_claims = decode_access_token(refreshed_brand_access)
    assert refreshed_brand_claims["exp"] <= int(sandbox_expires_at.timestamp())
    assert refreshed_brand_claims["demo_session_id"] == first_brand_session_id
    async with AsyncSessionLocal() as db:
        refreshed_brand_session = await db.scalar(
            select(UserToken).where(
                UserToken.user_id == brand_user_id,
                UserToken.token_type == TOKEN_TYPE_REFRESH,
                UserToken.revoked_at.is_(None),
            )
        )
        assert refreshed_brand_session is not None
        assert refreshed_brand_session.expires_at <= sandbox_expires_at

    to_agency = await client.post(
        "/api/v1/demo/switch-portal",
        json={"portal": "agency"},
        headers={"Authorization": f"Bearer {refreshed_brand_access}"},
    )
    assert to_agency.status_code == 200
    agency_payload = to_agency.json()
    assert agency_payload["portal"] == "agency"
    assert agency_payload["redirect_to"] == "/dashboard"
    new_agency_access = agency_payload["access_token"]
    new_agency_claims = decode_access_token(new_agency_access)
    assert new_agency_claims["sub"] == str(agency_user_id)
    assert new_agency_claims["exp"] <= int(sandbox_expires_at.timestamp())
    assert new_agency_claims["demo_session_id"] != initial_agency_session_id

    stale_brand = await client.get("/api/v1/auth/me", headers=brand_headers)
    assert stale_brand.status_code == 401

    new_agency_headers = {"Authorization": f"Bearer {new_agency_access}"}
    stale_agency_after_reactivation = await client.get("/api/v1/auth/me", headers=agency_headers)
    assert stale_agency_after_reactivation.status_code == 401
    new_agency_me = await client.get("/api/v1/auth/me", headers=new_agency_headers)
    assert new_agency_me.status_code == 200
    switched_session = await client.get("/api/v1/demo/session", headers=new_agency_headers)
    assert switched_session.status_code == 200
    assert switched_session.json()["active_portal"] == "agency"
    denied_brand = await client.get("/api/v1/brand-portal/me", headers=new_agency_headers)
    assert denied_brand.status_code == 403

    to_brand_again = await client.post(
        "/api/v1/demo/switch-portal",
        json={"portal": "brand"},
        headers=new_agency_headers,
    )
    assert to_brand_again.status_code == 200
    second_brand_access = to_brand_again.json()["access_token"]
    second_brand_claims = decode_access_token(second_brand_access)
    assert second_brand_claims["demo_session_id"] != first_brand_session_id
    stale_brand_after_reactivation = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refreshed_brand_access}"},
    )
    assert stale_brand_after_reactivation.status_code == 401
    second_brand_headers = {"Authorization": f"Bearer {second_brand_access}"}
    second_brand_me = await client.get("/api/v1/auth/me", headers=second_brand_headers)
    assert second_brand_me.status_code == 200

    final_to_agency = await client.post(
        "/api/v1/demo/switch-portal",
        json={"portal": "agency"},
        headers=second_brand_headers,
    )
    assert final_to_agency.status_code == 200
    final_agency_access = final_to_agency.json()["access_token"]
    final_agency_claims = decode_access_token(final_agency_access)
    assert final_agency_claims["demo_session_id"] != new_agency_claims["demo_session_id"]
    final_agency_me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {final_agency_access}"},
    )
    assert final_agency_me.status_code == 200

    async with AsyncSessionLocal() as db:
        active_refresh_users = list(
            (
                await db.execute(
                    select(UserToken.user_id).where(
                        UserToken.user_id.in_([agency_user_id, brand_user_id]),
                        UserToken.token_type == TOKEN_TYPE_REFRESH,
                        UserToken.revoked_at.is_(None),
                    )
                )
            ).scalars()
        )
        assert active_refresh_users == [agency_user_id]
        active_refresh = await db.scalar(
            select(UserToken).where(
                UserToken.user_id == agency_user_id,
                UserToken.token_type == TOKEN_TYPE_REFRESH,
                UserToken.revoked_at.is_(None),
            )
        )
        assert active_refresh is not None
        assert active_refresh.expires_at <= sandbox_expires_at
        identity_states = dict(
            (
                await db.execute(
                    select(User.id, User.is_active).where(
                        User.id.in_([agency_user_id, brand_user_id])
                    )
                )
            ).all()
        )
        assert identity_states == {agency_user_id: True, brand_user_id: False}
        membership_agency_id = await db.scalar(
            select(Brand.agency_id)
            .join(BrandMember, BrandMember.brand_id == Brand.id)
            .where(BrandMember.user_id == brand_user_id)
        )
        assert membership_agency_id == agency_id


async def test_demo_brand_invitation_mutations_are_blocked_before_persistence(
    client: AsyncClient,
) -> None:
    await _enable_demo()
    async with AsyncSessionLocal() as db:
        sandbox, agency_access, _ = await DemoSandboxService(db).create(
            ip_address="203.0.113.12",
            user_agent="pytest",
            turnstile_token=None,
        )
        assert sandbox.brand_user_id is not None
        brands = list(
            (
                await db.execute(
                    select(Brand)
                    .where(Brand.agency_id == sandbox.agency_id)
                    .order_by(Brand.created_at)
                )
            ).scalars()
        )
        assert len(brands) >= 2
        brand_user = await db.get(User, sandbox.brand_user_id)
        assert brand_user is not None
        brand_user_email = brand_user.email
        primary_brand_id = await db.scalar(
            select(BrandMember.brand_id).where(BrandMember.user_id == brand_user.id)
        )
        assert primary_brand_id is not None
        secondary_brand_id = next(brand.id for brand in brands if brand.id != primary_brand_id)

    switch_response = await client.post(
        "/api/v1/demo/switch-portal",
        json={"portal": "brand"},
        headers={"Authorization": f"Bearer {agency_access}"},
    )
    assert switch_response.status_code == 200
    brand_access = switch_response.json()["access_token"]
    brand_headers = {"Authorization": f"Bearer {brand_access}"}

    create_response = await client.post(
        "/api/v1/brand-portal/team/invite",
        json={"email": "outside@example.com", "role": "brand_viewer"},
        headers=brand_headers,
    )
    assert create_response.status_code == 403

    resend_token = generate_token()
    accept_token = generate_token()
    async with AsyncSessionLocal() as db:
        resend_invitation = Invitation(
            agency_id=sandbox.agency_id,
            brand_id=primary_brand_id,
            invitation_type="brand",
            email="outside@example.com",
            role=BrandMemberRole.BRAND_VIEWER.value,
            token_hash=hash_token(resend_token),
            invited_by=sandbox.owner_user_id,
            expires_at=sandbox.expires_at,
        )
        accept_invitation = Invitation(
            agency_id=sandbox.agency_id,
            brand_id=secondary_brand_id,
            invitation_type="brand",
            email=brand_user_email,
            role=BrandMemberRole.BRAND_VIEWER.value,
            token_hash=hash_token(accept_token),
            invited_by=sandbox.owner_user_id,
            expires_at=sandbox.expires_at,
        )
        db.add_all([resend_invitation, accept_invitation])
        await db.commit()
        await db.refresh(resend_invitation)
        await db.refresh(accept_invitation)
        resend_invitation_id = resend_invitation.id
        accept_invitation_id = accept_invitation.id
        original_resend_hash = resend_invitation.token_hash

    resend_response = await client.post(
        f"/api/v1/brand-portal/team/invitations/{resend_invitation_id}/resend",
        headers=brand_headers,
    )
    assert resend_response.status_code == 403
    accept_response = await client.post(
        f"/api/v1/invitations/{accept_invitation_id}/accept",
        headers=brand_headers,
    )
    assert accept_response.status_code == 403

    async with AsyncSessionLocal() as db:
        resend_invitation = await db.get(Invitation, resend_invitation_id)
        accept_invitation = await db.get(Invitation, accept_invitation_id)
        assert resend_invitation is not None
        assert resend_invitation.token_hash == original_resend_hash
        assert resend_invitation.resent_count == 0
        assert accept_invitation is not None
        assert accept_invitation.accepted_at is None
        membership_count = await db.scalar(
            select(func.count(BrandMember.id)).where(
                BrandMember.user_id == sandbox.brand_user_id,
                BrandMember.deleted_at.is_(None),
            )
        )
        invitation_count = await db.scalar(
            select(func.count(Invitation.id)).where(
                Invitation.agency_id == sandbox.agency_id,
                Invitation.deleted_at.is_(None),
            )
        )
        assert membership_count == 1
        assert invitation_count == 2


async def test_demo_portal_switch_forbids_non_demo_user(client: AsyncClient) -> None:
    user_id: uuid.UUID | None = None
    try:
        async with AsyncSessionLocal() as db:
            user = User(
                email=f"non-demo-switch-{uuid.uuid4().hex}@test.local",
                password_hash="x",
                full_name="Non Demo User",
                user_type=UserType.AGENCY_USER.value,
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            user_id = user.id

        response = await client.post(
            "/api/v1/demo/switch-portal",
            json={"portal": "brand"},
            headers={"Authorization": f"Bearer {create_access_token(str(user_id))}"},
        )
        assert response.status_code == 403
    finally:
        if user_id is not None:
            async with AsyncSessionLocal() as db:
                await db.execute(delete(User).where(User.id == user_id))
                await db.commit()


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
        assert sandbox.brand_user_id is not None
        brand_refresh = generate_token()
        db.add(
            UserToken(
                user_id=sandbox.brand_user_id,
                token_hash=hash_token(brand_refresh),
                token_family=new_token_family(),
                token_type=TOKEN_TYPE_REFRESH,
                expires_at=sandbox.expires_at,
            )
        )
        await db.flush()
        await DemoSandboxService(db).terminate(sandbox, reason="platform_admin")
        await db.commit()

        agency = await db.get(Agency, sandbox.agency_id)
        user = await db.get(User, sandbox.owner_user_id)
        brand_user = await db.get(User, sandbox.brand_user_id)
        assert sandbox.status == "terminated"
        assert agency is not None and agency.status == AgencyStatus.SUSPENDED.value
        assert user is not None and user.is_active is False
        assert brand_user is not None and brand_user.is_active is False
        active_tokens = await db.scalar(
            select(func.count(UserToken.id)).where(
                UserToken.user_id.in_([sandbox.owner_user_id, sandbox.brand_user_id]),
                UserToken.revoked_at.is_(None),
            )
        )
        assert active_tokens == 0
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
        assert sandbox.brand_user_id is not None
        agency = await db.get(Agency, sandbox.agency_id)
        assert agency is not None
        sandbox.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await db.commit()
        for user_id in (sandbox.owner_user_id, sandbox.brand_user_id):
            with pytest.raises(HTTPException) as exc_info:
                await ensure_demo_user_access(db, user_id)
            assert exc_info.value.status_code == 401

        assert await terminate_expired_sandboxes(db) == 1
        owner = await db.get(User, sandbox.owner_user_id)
        brand_user = await db.get(User, sandbox.brand_user_id)
        assert sandbox.status == "expired"
        assert owner is not None and owner.is_active is False
        assert brand_user is not None and brand_user.is_active is False


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
    growth_before = await client.get("/api/v1/platform/growth/metrics", headers=headers)
    subscriptions_before = await client.get("/api/v1/platform/subscriptions", headers=headers)
    assert growth_before.status_code == subscriptions_before.status_code == 200

    async with AsyncSessionLocal() as db:
        sandbox, _, _ = await DemoSandboxService(db).create(
            ip_address="203.0.113.60",
            user_agent="pytest",
            turnstile_token=None,
        )
        demo_agency_id = str(sandbox.agency_id)
        demo_user_id = str(sandbox.owner_user_id)
        assert sandbox.brand_user_id is not None
        demo_brand_user_id = str(sandbox.brand_user_id)

    after = await client.get("/api/v1/platform/dashboard", headers=headers)
    assert after.status_code == 200
    assert after.json() == before.json()
    growth_after = await client.get("/api/v1/platform/growth/metrics", headers=headers)
    subscriptions_after = await client.get("/api/v1/platform/subscriptions", headers=headers)
    assert growth_after.status_code == subscriptions_after.status_code == 200
    assert growth_after.json() == growth_before.json()
    assert subscriptions_after.json() == subscriptions_before.json()

    agencies = await client.get("/api/v1/platform/agencies", headers=headers)
    brands = await client.get("/api/v1/platform/brands", headers=headers)
    users = await client.get("/api/v1/platform/users", headers=headers)
    assert agencies.status_code == brands.status_code == users.status_code == 200
    assert demo_agency_id not in {item["id"] for item in agencies.json()}
    assert all(item["agency_id"] != demo_agency_id for item in brands.json())
    assert demo_user_id not in {item["id"] for item in users.json()}
    assert demo_brand_user_id not in {item["id"] for item in users.json()}

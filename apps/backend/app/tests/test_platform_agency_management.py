"""Integration tests for platform-admin agency management extensions:
member role/status changes (with last-owner protection), plan changes,
read-only branding visibility, and the agency-scoped audit feed.

Requires a live Postgres test DB (see conftest.py DATABASE_URL default).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.enums import AgencyMemberRole, AgencyMemberStatus, UserType
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User


def _admin_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _make_user(session, email: str, user_type: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash="not-a-real-hash-test-fixture-only",
        full_name="Fixture User",
        user_type=user_type,
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    return user


@dataclass
class AgencyCtx:
    admin_token: str
    agency_id: uuid.UUID
    owner_member_id: uuid.UUID
    owner_user_id: uuid.UUID
    admin_member_id: uuid.UUID
    plan_a_id: uuid.UUID
    plan_b_id: uuid.UUID
    user_ids: list[uuid.UUID]


@pytest.fixture
async def agency_ctx():
    async with AsyncSessionLocal() as session:
        suffix = uuid.uuid4().hex[:10]

        platform_admin = await _make_user(
            session, f"padmin-{suffix}@test.local", UserType.PLATFORM_ADMIN.value
        )
        owner_user = await _make_user(
            session, f"owner-{suffix}@test.local", UserType.AGENCY_USER.value
        )
        admin_user = await _make_user(
            session, f"admin-{suffix}@test.local", UserType.AGENCY_USER.value
        )
        await session.flush()

        plan_a = Plan(
            id=uuid.uuid4(),
            code=f"starter-{suffix}",
            name="Starter Test",
            monthly_price_cents=0,
            yearly_price_cents=0,
        )
        plan_b = Plan(
            id=uuid.uuid4(),
            code=f"pro-{suffix}",
            name="Pro Test",
            monthly_price_cents=9900,
            yearly_price_cents=99000,
            white_label_enabled=True,
        )
        session.add_all([plan_a, plan_b])
        await session.flush()

        agency = Agency(
            id=uuid.uuid4(),
            name=f"Agency {suffix}",
            slug=f"agency-{suffix}",
            owner_user_id=owner_user.id,
            plan_id=plan_a.id,
        )
        session.add(agency)
        await session.flush()

        subscription = Subscription(
            id=uuid.uuid4(),
            agency_id=agency.id,
            plan_id=plan_a.id,
            status="active",
        )
        owner_member = AgencyMember(
            id=uuid.uuid4(),
            agency_id=agency.id,
            user_id=owner_user.id,
            role=AgencyMemberRole.OWNER.value,
            status=AgencyMemberStatus.ACTIVE.value,
        )
        admin_member = AgencyMember(
            id=uuid.uuid4(),
            agency_id=agency.id,
            user_id=admin_user.id,
            role=AgencyMemberRole.ADMIN.value,
            status=AgencyMemberStatus.ACTIVE.value,
        )
        session.add_all([subscription, owner_member, admin_member])
        await session.commit()

        token = create_access_token(
            str(platform_admin.id), extra_claims={"user_type": UserType.PLATFORM_ADMIN.value}
        )

        ctx = AgencyCtx(
            admin_token=token,
            agency_id=agency.id,
            owner_member_id=owner_member.id,
            owner_user_id=owner_user.id,
            admin_member_id=admin_member.id,
            plan_a_id=plan_a.id,
            plan_b_id=plan_b.id,
            user_ids=[platform_admin.id, owner_user.id, admin_user.id],
        )
        try:
            yield ctx
        finally:
            agency_row = await session.get(Agency, agency.id)
            if agency_row is not None:
                await session.delete(agency_row)
            await session.commit()
            for pid in (plan_a.id, plan_b.id):
                plan_row = await session.get(Plan, pid)
                if plan_row is not None:
                    await session.delete(plan_row)
            await session.commit()
            # platform_admin is intentionally excluded: platform_audit_logs.admin_user_id
            # is ON DELETE RESTRICT and audit rows are immutable (insert-only, enforced by
            # a DB trigger), so any admin that acted during the test can never be deleted.
            for uid in (owner_user.id, admin_user.id):
                user_row = await session.get(User, uid)
                if user_row is not None:
                    await session.delete(user_row)
            await session.commit()


class TestAgencyMemberRoleChange:
    async def test_change_admin_member_role_succeeds(
        self, client: AsyncClient, agency_ctx: AgencyCtx
    ) -> None:
        resp = await client.patch(
            f"/api/v1/platform/agencies/{agency_ctx.agency_id}/members/{agency_ctx.admin_member_id}",
            json={"role": "brand_manager"},
            headers=_admin_headers(agency_ctx.admin_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["role"] == "brand_manager"

    async def test_cannot_strip_last_active_owner(
        self, client: AsyncClient, agency_ctx: AgencyCtx
    ) -> None:
        resp = await client.patch(
            f"/api/v1/platform/agencies/{agency_ctx.agency_id}/members/{agency_ctx.owner_member_id}",
            json={"role": "admin"},
            headers=_admin_headers(agency_ctx.admin_token),
        )
        assert resp.status_code == 400
        assert "owner" in resp.json()["detail"].lower() or "sahi" in resp.json()["detail"].lower()

    async def test_cannot_suspend_last_active_owner(
        self, client: AsyncClient, agency_ctx: AgencyCtx
    ) -> None:
        resp = await client.patch(
            f"/api/v1/platform/agencies/{agency_ctx.agency_id}/members/{agency_ctx.owner_member_id}",
            json={"status": "suspended"},
            headers=_admin_headers(agency_ctx.admin_token),
        )
        assert resp.status_code == 400

    async def test_can_demote_owner_when_second_owner_exists(
        self, client: AsyncClient, agency_ctx: AgencyCtx
    ) -> None:
        # Promote the admin member to a second owner first.
        promote = await client.patch(
            f"/api/v1/platform/agencies/{agency_ctx.agency_id}/members/{agency_ctx.admin_member_id}",
            json={"role": "owner"},
            headers=_admin_headers(agency_ctx.admin_token),
        )
        assert promote.status_code == 200

        demote = await client.patch(
            f"/api/v1/platform/agencies/{agency_ctx.agency_id}/members/{agency_ctx.owner_member_id}",
            json={"role": "admin"},
            headers=_admin_headers(agency_ctx.admin_token),
        )
        assert demote.status_code == 200
        assert demote.json()["role"] == "admin"

    async def test_invalid_role_rejected(self, client: AsyncClient, agency_ctx: AgencyCtx) -> None:
        resp = await client.patch(
            f"/api/v1/platform/agencies/{agency_ctx.agency_id}/members/{agency_ctx.admin_member_id}",
            json={"role": "superuser"},
            headers=_admin_headers(agency_ctx.admin_token),
        )
        assert resp.status_code == 422

    async def test_member_not_found_returns_404(
        self, client: AsyncClient, agency_ctx: AgencyCtx
    ) -> None:
        resp = await client.patch(
            f"/api/v1/platform/agencies/{agency_ctx.agency_id}/members/{uuid.uuid4()}",
            json={"role": "admin"},
            headers=_admin_headers(agency_ctx.admin_token),
        )
        assert resp.status_code == 404

    async def test_non_admin_forbidden(self, client: AsyncClient, agency_ctx: AgencyCtx) -> None:
        non_admin_token = create_access_token(
            str(agency_ctx.owner_user_id), extra_claims={"user_type": UserType.AGENCY_USER.value}
        )
        resp = await client.patch(
            f"/api/v1/platform/agencies/{agency_ctx.agency_id}/members/{agency_ctx.admin_member_id}",
            json={"role": "admin"},
            headers=_admin_headers(non_admin_token),
        )
        assert resp.status_code == 403


class TestAgencyPlanChange:
    async def test_change_plan_succeeds(self, client: AsyncClient, agency_ctx: AgencyCtx) -> None:
        resp = await client.patch(
            f"/api/v1/platform/agencies/{agency_ctx.agency_id}/plan",
            json={"plan_id": str(agency_ctx.plan_b_id), "reason": "Upgrade requested"},
            headers=_admin_headers(agency_ctx.admin_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["plan_code"].startswith("pro-")

    async def test_unknown_plan_returns_404(
        self, client: AsyncClient, agency_ctx: AgencyCtx
    ) -> None:
        resp = await client.patch(
            f"/api/v1/platform/agencies/{agency_ctx.agency_id}/plan",
            json={"plan_id": str(uuid.uuid4())},
            headers=_admin_headers(agency_ctx.admin_token),
        )
        assert resp.status_code == 404


class TestAgencyBrandingVisibility:
    async def test_get_branding_defaults_when_unconfigured(
        self, client: AsyncClient, agency_ctx: AgencyCtx
    ) -> None:
        resp = await client.get(
            f"/api/v1/platform/agencies/{agency_ctx.agency_id}/branding",
            headers=_admin_headers(agency_ctx.admin_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["branding"]["is_white_label_enabled"] is False
        assert body["domain"] is None
        # Never leak internal asset storage paths as raw filesystem locations
        assert "storage_key" not in body["branding"]


class TestAgencyAuditFeed:
    async def test_audit_feed_reflects_suspend_and_member_change(
        self, client: AsyncClient, agency_ctx: AgencyCtx
    ) -> None:
        suspend = await client.post(
            f"/api/v1/platform/agencies/{agency_ctx.agency_id}/suspend",
            json={"reason": "Test suspension"},
            headers=_admin_headers(agency_ctx.admin_token),
        )
        assert suspend.status_code == 204

        reactivate = await client.post(
            f"/api/v1/platform/agencies/{agency_ctx.agency_id}/reactivate",
            headers=_admin_headers(agency_ctx.admin_token),
        )
        assert reactivate.status_code == 204

        role_change = await client.patch(
            f"/api/v1/platform/agencies/{agency_ctx.agency_id}/members/{agency_ctx.admin_member_id}",
            json={"role": "viewer"},
            headers=_admin_headers(agency_ctx.admin_token),
        )
        assert role_change.status_code == 200

        feed = await client.get(
            f"/api/v1/platform/agencies/{agency_ctx.agency_id}/audit",
            headers=_admin_headers(agency_ctx.admin_token),
        )
        assert feed.status_code == 200
        actions = [entry["action"] for entry in feed.json()]
        assert "agency.suspended" in actions
        assert "agency.reactivated" in actions
        assert "agency_member.updated" in actions

    async def test_audit_feed_requires_platform_admin(
        self, client: AsyncClient, agency_ctx: AgencyCtx
    ) -> None:
        non_admin_token = create_access_token(
            str(agency_ctx.owner_user_id), extra_claims={"user_type": UserType.AGENCY_USER.value}
        )
        resp = await client.get(
            f"/api/v1/platform/agencies/{agency_ctx.agency_id}/audit",
            headers=_admin_headers(non_admin_token),
        )
        assert resp.status_code == 403

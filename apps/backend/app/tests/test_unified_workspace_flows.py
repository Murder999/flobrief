"""Integration coverage for unified identity, solo-brand team, billing and partnerships."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.brand import Brand
from app.models.brand_member import BrandMember
from app.models.enums import (
    AgencyMemberRole,
    AgencyMemberStatus,
    BrandMemberRole,
    BrandMemberStatus,
    UserType,
)
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.auth import RegisterRequest
from app.services import email_service
from app.services.auth_service import AuthService
from app.services.invitation_service import InvitationService


@dataclass
class UnifiedContext:
    agency_id: uuid.UUID
    brand_id: uuid.UUID
    plan_id: uuid.UUID
    agency_owner_id: uuid.UUID
    brand_owner_id: uuid.UUID
    brand_manager_id: uuid.UUID
    recipient_id: uuid.UUID
    agency_owner_token: str
    brand_owner_token: str
    brand_manager_token: str
    recipient_token: str
    brand_owner_email: str
    recipient_email: str
    membership_invite_token: str | None = None
    partnership_invite_token: str | None = None


def _headers(token: str, *, agency_id: uuid.UUID | None = None, brand_id: uuid.UUID | None = None):
    headers = {"Authorization": f"Bearer {token}"}
    if agency_id is not None:
        headers["X-Agency-ID"] = str(agency_id)
    if brand_id is not None:
        headers["X-Brand-ID"] = str(brand_id)
    return headers


@pytest.fixture
async def unified_context(monkeypatch: pytest.MonkeyPatch):
    suffix = uuid.uuid4().hex[:10]

    async def capture_membership_invite(*args, **kwargs) -> None:
        ctx.membership_invite_token = kwargs["token"]

    async def capture_partnership_invite(*args, **kwargs) -> None:
        ctx.partnership_invite_token = kwargs["token"]

    async with AsyncSessionLocal() as session:
        agency_owner = User(
            email=f"agency-owner-{suffix}@example.com",
            password_hash="not-a-real-hash-test-fixture-only",
            full_name="Agency Owner",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        brand_owner = User(
            email=f"brand-owner-{suffix}@example.com",
            password_hash="not-a-real-hash-test-fixture-only",
            full_name="Brand Owner",
            user_type=UserType.BRAND_USER.value,
            is_active=True,
            is_verified=True,
        )
        brand_manager = User(
            email=f"brand-manager-{suffix}@example.com",
            password_hash="not-a-real-hash-test-fixture-only",
            full_name="Brand Manager",
            user_type=UserType.BRAND_USER.value,
            is_active=True,
            is_verified=True,
        )
        recipient = User(
            email=f"recipient-{suffix}@example.com",
            password_hash="not-a-real-hash-test-fixture-only",
            full_name="Recipient",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        plan = Plan(
            code=f"brand-solo-test-{suffix}",
            name="Brand Solo Test",
            monthly_price_cents=9900,
            yearly_price_cents=99000,
            max_brands=1,
            max_users=5,
            max_brand_users=5,
            max_pending_agency_invites=5,
            max_pending_brand_invites=5,
        )
        session.add_all([agency_owner, brand_owner, brand_manager, recipient, plan])
        await session.flush()

        agency = Agency(
            name=f"Agency {suffix}",
            slug=f"agency-{suffix}",
            owner_user_id=agency_owner.id,
            status="active",
        )
        brand = Brand(
            agency_id=None,
            name=f"Independent Brand {suffix}",
            slug=f"independent-brand-{suffix}",
            status="active",
        )
        session.add_all([agency, brand])
        await session.flush()
        session.add_all(
            [
                AgencyMember(
                    agency_id=agency.id,
                    user_id=agency_owner.id,
                    role=AgencyMemberRole.OWNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
                BrandMember(
                    brand_id=brand.id,
                    user_id=brand_owner.id,
                    role=BrandMemberRole.BRAND_OWNER.value,
                    status=BrandMemberStatus.ACTIVE.value,
                ),
                BrandMember(
                    brand_id=brand.id,
                    user_id=brand_manager.id,
                    role=BrandMemberRole.BRAND_MANAGER.value,
                    status=BrandMemberStatus.ACTIVE.value,
                ),
                Subscription(
                    brand_id=brand.id,
                    plan_id=plan.id,
                    status="active",
                    billing_provider="manual",
                ),
            ]
        )
        await session.commit()

        ctx = UnifiedContext(
            agency_id=agency.id,
            brand_id=brand.id,
            plan_id=plan.id,
            agency_owner_id=agency_owner.id,
            brand_owner_id=brand_owner.id,
            brand_manager_id=brand_manager.id,
            recipient_id=recipient.id,
            agency_owner_token=create_access_token(str(agency_owner.id)),
            brand_owner_token=create_access_token(str(brand_owner.id)),
            brand_manager_token=create_access_token(str(brand_manager.id)),
            recipient_token=create_access_token(str(recipient.id)),
            brand_owner_email=brand_owner.email,
            recipient_email=recipient.email,
        )
        monkeypatch.setattr(
            InvitationService,
            "_send_brand_invite_email",
            capture_membership_invite,
        )
        monkeypatch.setattr(
            email_service,
            "send_partnership_invite_email",
            capture_partnership_invite,
        )
        yield ctx

        persisted_agency = await session.get(Agency, agency.id)
        if persisted_agency is not None:
            await session.delete(persisted_agency)
        persisted_brand = await session.get(Brand, brand.id)
        if persisted_brand is not None:
            await session.delete(persisted_brand)
        await session.commit()
        persisted_plan = await session.get(Plan, plan.id)
        if persisted_plan is not None:
            await session.delete(persisted_plan)
        for user in (agency_owner, brand_owner, brand_manager, recipient):
            persisted_user = await session.get(User, user.id)
            if persisted_user is not None:
                await session.delete(persisted_user)
        await session.commit()


async def test_independent_brand_can_invite_cross_portal_account(
    client: AsyncClient, unified_context: UnifiedContext
) -> None:
    ctx = unified_context
    response = await client.post(
        "/api/v1/brand-portal/team/invite",
        json={"email": ctx.recipient_email, "role": "brand_viewer"},
        headers=_headers(ctx.brand_owner_token, brand_id=ctx.brand_id),
    )
    assert response.status_code == 201
    assert response.json()["agency_id"] is None
    assert ctx.membership_invite_token is not None

    preview = await client.get(f"/api/v1/invitations/preview/{ctx.membership_invite_token}")
    assert preview.status_code == 200
    assert preview.json()["brand_name"].startswith("Independent Brand")

    accepted = await client.post(
        f"/api/v1/invitations/accept/{ctx.membership_invite_token}",
        headers=_headers(ctx.recipient_token),
    )
    assert accepted.status_code == 204
    async with AsyncSessionLocal() as session:
        membership = await session.scalar(
            select(BrandMember).where(
                BrandMember.brand_id == ctx.brand_id,
                BrandMember.user_id == ctx.recipient_id,
            )
        )
        assert membership is not None
        assert membership.role == BrandMemberRole.BRAND_VIEWER.value


async def test_brand_billing_is_scoped_to_brand_owner(
    client: AsyncClient, unified_context: UnifiedContext
) -> None:
    ctx = unified_context
    owner = await client.get(
        "/api/v1/brand-portal/billing/subscription",
        headers=_headers(ctx.brand_owner_token, brand_id=ctx.brand_id),
    )
    assert owner.status_code == 200
    assert owner.json()["brand_id"] == str(ctx.brand_id)
    assert owner.json()["agency_id"] is None

    manager = await client.get(
        "/api/v1/brand-portal/billing/subscription",
        headers=_headers(ctx.brand_manager_token, brand_id=ctx.brand_id),
    )
    assert manager.status_code == 403


async def test_partnership_acceptance_links_workspaces_without_team_membership(
    client: AsyncClient, unified_context: UnifiedContext
) -> None:
    ctx = unified_context
    created = await client.post(
        "/api/v1/partnership-invitations/agency",
        json={"email": ctx.brand_owner_email},
        headers=_headers(ctx.agency_owner_token, agency_id=ctx.agency_id),
    )
    assert created.status_code == 201
    assert ctx.partnership_invite_token is not None

    accepted = await client.post(
        f"/api/v1/partnership-invitations/accept/{ctx.partnership_invite_token}",
        json={"target_workspace_id": str(ctx.brand_id)},
        headers=_headers(ctx.brand_owner_token),
    )
    assert accepted.status_code == 200
    assert accepted.json()["agency_id"] == str(ctx.agency_id)
    assert accepted.json()["brand_id"] == str(ctx.brand_id)

    async with AsyncSessionLocal() as session:
        brand = await session.get(Brand, ctx.brand_id)
        agency_membership = await session.scalar(
            select(AgencyMember).where(
                AgencyMember.agency_id == ctx.agency_id,
                AgencyMember.user_id == ctx.brand_owner_id,
            )
        )
        assert brand is not None and brand.agency_id == ctx.agency_id
        assert agency_membership is None


@pytest.mark.parametrize("workspace_type", ["agency", "brand"])
async def test_registration_creates_selected_owner_workspace(workspace_type: str) -> None:
    suffix = uuid.uuid4().hex[:10]
    async with AsyncSessionLocal() as session:
        user = await AuthService(session).register(
            RegisterRequest(
                email=f"register-{workspace_type}-{suffix}@example.com",
                full_name="Registration Owner",
                password="SecureRegistration@2026",
                workspace_type=workspace_type,
                workspace_name=f"Registration {workspace_type.title()} {suffix}",
            )
        )

        if workspace_type == "agency":
            membership = await session.scalar(
                select(AgencyMember).where(AgencyMember.user_id == user.id)
            )
            assert user.user_type == UserType.AGENCY_USER.value
            assert membership is not None
            assert membership.role == AgencyMemberRole.OWNER.value
            workspace = await session.get(Agency, membership.agency_id)
        else:
            membership = await session.scalar(
                select(BrandMember).where(BrandMember.user_id == user.id)
            )
            assert user.user_type == UserType.BRAND_USER.value
            assert membership is not None
            assert membership.role == BrandMemberRole.BRAND_OWNER.value
            workspace = await session.get(Brand, membership.brand_id)
            assert workspace is not None and workspace.agency_id is None

        assert workspace is not None
        await session.delete(workspace)
        await session.commit()
        persisted_user = await session.get(User, user.id)
        if persisted_user is not None:
            await session.delete(persisted_user)
        await session.commit()

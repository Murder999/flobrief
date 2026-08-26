"""Integration tests for Platform Admin agency/brand provisioning and recovery."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.brand_member import BrandMember
from app.models.enums import UserType
from app.models.invitation import Invitation
from app.models.plan import Plan
from app.models.platform_audit_log import PlatformAuditLog
from app.models.subscription import Subscription
from app.models.user import User
from app.services.invitation_service import InvitationService


@dataclass
class PlatformContext:
    admin_token: str
    agency_token: str
    brand_token: str
    plan_id: uuid.UUID
    base_agency_id: uuid.UUID
    agency_user_email: str
    brand_user_email: str
    incompatible_email: str
    created_agency_ids: list[uuid.UUID] = field(default_factory=list)
    user_ids: list[uuid.UUID] = field(default_factory=list)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _make_user(session, suffix: str, label: str, user_type: str) -> User:
    user = User(
        email=f"{label}-{suffix}@example.com",
        password_hash="not-a-real-hash-test-fixture-only",
        full_name=f"{label.title()} User",
        user_type=user_type,
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    return user


@pytest.fixture
async def platform_context(monkeypatch: pytest.MonkeyPatch):
    async def _skip_email(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr(InvitationService, "send_invitation_email", _skip_email)
    suffix = uuid.uuid4().hex[:10]
    async with AsyncSessionLocal() as session:
        admin = await _make_user(session, suffix, "platform-admin", UserType.PLATFORM_ADMIN.value)
        agency_user = await _make_user(session, suffix, "agency-user", UserType.AGENCY_USER.value)
        brand_user = await _make_user(session, suffix, "brand-user", UserType.BRAND_USER.value)
        incompatible = await _make_user(
            session, suffix, "incompatible-agency", UserType.AGENCY_USER.value
        )
        plan = Plan(
            code=f"platform-provision-{suffix}",
            name="Platform Provision Test",
            monthly_price_cents=0,
            yearly_price_cents=0,
            max_brands=20,
            max_users=20,
            max_brand_users=20,
            max_pending_agency_invites=20,
            max_pending_brand_invites=20,
        )
        session.add(plan)
        await session.flush()
        base_agency = Agency(
            name=f"Platform Base Agency {suffix}",
            slug=f"platform-base-{suffix}",
            plan_id=plan.id,
            is_demo=False,
        )
        session.add(base_agency)
        await session.flush()
        session.add(
            Subscription(
                agency_id=base_agency.id,
                plan_id=plan.id,
                status="active",
                billing_provider="manual",
            )
        )
        await session.commit()

        ctx = PlatformContext(
            admin_token=create_access_token(
                str(admin.id), extra_claims={"user_type": UserType.PLATFORM_ADMIN.value}
            ),
            agency_token=create_access_token(
                str(agency_user.id), extra_claims={"user_type": UserType.AGENCY_USER.value}
            ),
            brand_token=create_access_token(
                str(brand_user.id), extra_claims={"user_type": UserType.BRAND_USER.value}
            ),
            plan_id=plan.id,
            base_agency_id=base_agency.id,
            agency_user_email=agency_user.email,
            brand_user_email=brand_user.email,
            incompatible_email=incompatible.email,
            user_ids=[agency_user.id, brand_user.id, incompatible.id],
        )
        yield ctx

        for agency_id in [*ctx.created_agency_ids, base_agency.id]:
            agency = await session.get(Agency, agency_id)
            if agency is not None:
                await session.delete(agency)
        await session.commit()
        plan_row = await session.get(Plan, plan.id)
        if plan_row is not None:
            await session.delete(plan_row)
        await session.commit()
        for user_id in ctx.user_ids:
            user = await session.get(User, user_id)
            if user is not None:
                await session.delete(user)
        await session.commit()


def _agency_payload(ctx: PlatformContext, **changes) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": f"TEST Platform Agency {uuid.uuid4().hex[:8]}",
        "status": "active",
        "plan_id": str(ctx.plan_id),
        "locale": "tr",
        "owner_mode": "none",
    }
    payload.update(changes)
    return payload


def _brand_payload(ctx: PlatformContext, **changes) -> dict[str, object]:
    payload: dict[str, object] = {
        "agency_id": str(ctx.base_agency_id),
        "name": f"TEST Platform Brand {uuid.uuid4().hex[:8]}",
        "status": "active",
        "default_language": "en",
        "contact_mode": "none",
    }
    payload.update(changes)
    return payload


class TestPlatformAgencyProvisioning:
    async def test_create_agency_with_owner_invitation_and_manual_subscription(
        self, client: AsyncClient, platform_context: PlatformContext
    ) -> None:
        owner_email = f"new-owner-{uuid.uuid4().hex[:8]}@example.com"
        response = await client.post(
            "/api/v1/platform/agencies",
            json=_agency_payload(
                platform_context,
                owner_mode="invite",
                owner_email=owner_email,
            ),
            headers=_headers(platform_context.admin_token),
        )

        assert response.status_code == 201
        body = response.json()
        agency_id = uuid.UUID(body["agency"]["id"])
        platform_context.created_agency_ids.append(agency_id)
        assert body["owner_action"] == "invited"
        assert body["agency"]["owner_user_id"] is None
        async with AsyncSessionLocal() as session:
            invitation = await session.scalar(
                select(Invitation).where(
                    Invitation.agency_id == agency_id,
                    Invitation.email == owner_email,
                )
            )
            subscription = await session.scalar(
                select(Subscription).where(Subscription.agency_id == agency_id)
            )
            actions = set(
                await session.scalars(
                    select(PlatformAuditLog.action).where(
                        PlatformAuditLog.target_tenant_id == agency_id
                    )
                )
            )
            assert invitation is not None
            assert invitation.role == "owner"
            assert subscription is not None and subscription.billing_provider == "manual"
            assert "agency.created_by_platform" in actions
            assert "agency.owner_invited_by_platform" in actions
            assert await session.scalar(select(User).where(User.email == owner_email)) is None

    async def test_create_agency_attaches_confirmed_compatible_owner(
        self, client: AsyncClient, platform_context: PlatformContext
    ) -> None:
        response = await client.post(
            "/api/v1/platform/agencies",
            json=_agency_payload(
                platform_context,
                owner_mode="attach",
                owner_email=platform_context.agency_user_email,
                confirm_existing_user=True,
            ),
            headers=_headers(platform_context.admin_token),
        )

        assert response.status_code == 201
        body = response.json()
        agency_id = uuid.UUID(body["agency"]["id"])
        platform_context.created_agency_ids.append(agency_id)
        assert body["owner_action"] == "attached"
        assert body["agency"]["owner_user_id"] is not None
        async with AsyncSessionLocal() as session:
            member = await session.scalar(
                select(AgencyMember).where(AgencyMember.agency_id == agency_id)
            )
            assert member is not None and member.role == "owner"

    async def test_brand_preferred_user_can_own_agency_without_type_conversion(
        self, client: AsyncClient, platform_context: PlatformContext
    ) -> None:
        response = await client.post(
            "/api/v1/platform/agencies",
            json=_agency_payload(
                platform_context,
                owner_mode="attach",
                owner_email=platform_context.brand_user_email,
                confirm_existing_user=True,
            ),
            headers=_headers(platform_context.admin_token),
        )
        assert response.status_code == 201
        agency_id = uuid.UUID(response.json()["agency"]["id"])
        platform_context.created_agency_ids.append(agency_id)
        async with AsyncSessionLocal() as session:
            member = await session.scalar(
                select(AgencyMember).where(AgencyMember.agency_id == agency_id)
            )
            owner = await session.scalar(
                select(User).where(User.email == platform_context.brand_user_email)
            )
            assert member is not None and member.role == "owner"
            assert owner is not None and owner.user_type == UserType.BRAND_USER.value

    async def test_duplicate_names_receive_distinct_slugs(
        self, client: AsyncClient, platform_context: PlatformContext
    ) -> None:
        name = f"TEST Duplicate Agency {uuid.uuid4().hex[:8]}"
        first = await client.post(
            "/api/v1/platform/agencies",
            json=_agency_payload(platform_context, name=name),
            headers=_headers(platform_context.admin_token),
        )
        second = await client.post(
            "/api/v1/platform/agencies",
            json=_agency_payload(platform_context, name=name),
            headers=_headers(platform_context.admin_token),
        )
        assert first.status_code == second.status_code == 201
        platform_context.created_agency_ids.extend(
            [uuid.UUID(first.json()["agency"]["id"]), uuid.UUID(second.json()["agency"]["id"])]
        )
        assert first.json()["agency"]["slug"] != second.json()["agency"]["slug"]


class TestPlatformBrandProvisioning:
    async def test_create_brand_with_contact_invitation(
        self, client: AsyncClient, platform_context: PlatformContext
    ) -> None:
        email = f"new-brand-contact-{uuid.uuid4().hex[:8]}@example.com"
        response = await client.post(
            "/api/v1/platform/brands",
            json=_brand_payload(
                platform_context,
                contact_mode="invite",
                contact_email=email,
                contact_role="brand_manager",
            ),
            headers=_headers(platform_context.admin_token),
        )
        assert response.status_code == 201
        body = response.json()
        assert body["contact_action"] == "invited"
        brand_id = uuid.UUID(body["brand"]["id"])
        async with AsyncSessionLocal() as session:
            invitation = await session.scalar(
                select(Invitation).where(Invitation.brand_id == brand_id)
            )
            assert invitation is not None
            assert invitation.role == "brand_manager"
            actions = set(
                await session.scalars(
                    select(PlatformAuditLog.action).where(PlatformAuditLog.target_id == brand_id)
                )
            )
            assert "brand.created_by_platform" in actions
            assert "brand.user_invited_by_platform" in actions

    async def test_create_brand_attaches_confirmed_compatible_contact(
        self, client: AsyncClient, platform_context: PlatformContext
    ) -> None:
        response = await client.post(
            "/api/v1/platform/brands",
            json=_brand_payload(
                platform_context,
                contact_mode="attach",
                contact_email=platform_context.brand_user_email,
                contact_role="brand_owner",
                confirm_existing_user=True,
            ),
            headers=_headers(platform_context.admin_token),
        )
        assert response.status_code == 201
        brand_id = uuid.UUID(response.json()["brand"]["id"])
        async with AsyncSessionLocal() as session:
            member = await session.scalar(
                select(BrandMember).where(BrandMember.brand_id == brand_id)
            )
            assert member is not None and member.role == "brand_owner"


class TestPlatformRecoveryActions:
    async def test_agency_invitation_resend_and_revoke_are_audited(
        self, client: AsyncClient, platform_context: PlatformContext
    ) -> None:
        email = f"recovery-{uuid.uuid4().hex[:8]}@example.com"
        created = await client.post(
            f"/api/v1/platform/agencies/{platform_context.base_agency_id}/invitations",
            json={"email": email, "role": "admin", "locale": "en"},
            headers=_headers(platform_context.admin_token),
        )
        assert created.status_code == 201
        invitation_id = created.json()["id"]
        resent = await client.post(
            f"/api/v1/platform/agencies/{platform_context.base_agency_id}/invitations/{invitation_id}/resend",
            headers=_headers(platform_context.admin_token),
        )
        revoked = await client.post(
            f"/api/v1/platform/agencies/{platform_context.base_agency_id}/invitations/{invitation_id}/revoke",
            headers=_headers(platform_context.admin_token),
        )
        assert resent.status_code == 200
        assert resent.json()["resent_count"] == 1
        assert revoked.status_code == 204
        async with AsyncSessionLocal() as session:
            invitation = await session.get(Invitation, uuid.UUID(invitation_id))
            assert invitation is not None and invitation.revoked_at is not None
            actions = set(
                await session.scalars(
                    select(PlatformAuditLog.action).where(
                        PlatformAuditLog.target_id == invitation.id
                    )
                )
            )
            assert "invitation.resent_by_platform" in actions
            assert "invitation.revoked_by_platform" in actions

    async def test_attach_requires_confirmation_and_blocks_duplicate_membership(
        self, client: AsyncClient, platform_context: PlatformContext
    ) -> None:
        path = f"/api/v1/platform/agencies/{platform_context.base_agency_id}/members/attach"
        missing_confirmation = await client.post(
            path,
            json={"email": platform_context.agency_user_email, "role": "admin"},
            headers=_headers(platform_context.admin_token),
        )
        first = await client.post(
            path,
            json={
                "email": platform_context.agency_user_email,
                "role": "admin",
                "confirm_existing_user": True,
            },
            headers=_headers(platform_context.admin_token),
        )
        duplicate = await client.post(
            path,
            json={
                "email": platform_context.agency_user_email,
                "role": "admin",
                "confirm_existing_user": True,
            },
            headers=_headers(platform_context.admin_token),
        )
        assert missing_confirmation.status_code == 422
        assert first.status_code == 201
        assert duplicate.status_code == 409


class TestPlatformProvisioningAuthorization:
    @pytest.mark.parametrize("auth_kind", ["none", "agency", "brand"])
    async def test_customer_and_unauthenticated_callers_cannot_create_agency(
        self,
        client: AsyncClient,
        platform_context: PlatformContext,
        auth_kind: str,
    ) -> None:
        headers = {
            "none": {},
            "agency": _headers(platform_context.agency_token),
            "brand": _headers(platform_context.brand_token),
        }[auth_kind]
        response = await client.post(
            "/api/v1/platform/agencies",
            json=_agency_payload(platform_context),
            headers=headers,
        )
        assert response.status_code == (401 if auth_kind == "none" else 403)

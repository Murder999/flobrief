"""Integration coverage for invitation-aware account creation and acceptance."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.activity import ActivityLog
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
from app.models.invitation import Invitation
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.services.token_service import hash_token


@dataclass
class InviteContext:
    agency_id: uuid.UUID
    brand_id: uuid.UUID
    inviter_id: uuid.UUID
    plan_id: uuid.UUID
    user_ids: list[uuid.UUID]


@pytest.fixture
async def invite_context():
    suffix = uuid.uuid4().hex[:10]
    async with AsyncSessionLocal() as session:
        inviter = User(
            email=f"invite-owner-{suffix}@test.local",
            password_hash="not-a-real-hash-test-fixture-only",
            full_name="Invitation Owner",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        plan = Plan(
            code=f"invite-plan-{suffix}",
            name="Invitation Test Plan",
            monthly_price_cents=0,
            yearly_price_cents=0,
            max_users=20,
            max_brand_users=20,
            max_pending_agency_invites=20,
            max_pending_brand_invites=20,
        )
        session.add_all([inviter, plan])
        await session.flush()

        agency = Agency(
            name=f"Invitation Agency {suffix}",
            slug=f"invitation-agency-{suffix}",
            owner_user_id=inviter.id,
            plan_id=plan.id,
        )
        session.add(agency)
        await session.flush()
        brand = Brand(
            agency_id=agency.id,
            name=f"Invitation Brand {suffix}",
            slug=f"invitation-brand-{suffix}",
            default_language="en",
        )
        owner_member = AgencyMember(
            agency_id=agency.id,
            user_id=inviter.id,
            role=AgencyMemberRole.OWNER.value,
            status=AgencyMemberStatus.ACTIVE.value,
            joined_at=datetime.now(UTC),
        )
        subscription = Subscription(
            agency_id=agency.id,
            plan_id=plan.id,
            status="active",
        )
        session.add_all([brand, owner_member, subscription])
        await session.commit()

        ctx = InviteContext(
            agency_id=agency.id,
            brand_id=brand.id,
            inviter_id=inviter.id,
            plan_id=plan.id,
            user_ids=[inviter.id],
        )
        yield ctx

        agency_row = await session.get(Agency, agency.id)
        if agency_row is not None:
            await session.delete(agency_row)
            await session.commit()
        plan_row = await session.get(Plan, plan.id)
        if plan_row is not None:
            await session.delete(plan_row)
            await session.commit()
        for user_id in ctx.user_ids:
            user_row = await session.get(User, user_id)
            if user_row is not None:
                await session.delete(user_row)
        await session.commit()


async def _create_invitation(
    ctx: InviteContext,
    *,
    invitation_type: str,
    email: str,
    role: str,
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
    rejected_at: datetime | None = None,
) -> tuple[uuid.UUID, str]:
    token = f"invite-{uuid.uuid4().hex}-{uuid.uuid4().hex}"
    async with AsyncSessionLocal() as session:
        invitation = Invitation(
            agency_id=ctx.agency_id,
            brand_id=ctx.brand_id if invitation_type == "brand" else None,
            invitation_type=invitation_type,
            email=email,
            role=role,
            token_hash=hash_token(token),
            invited_by=ctx.inviter_id,
            expires_at=expires_at or datetime.now(UTC) + timedelta(days=7),
            revoked_at=revoked_at,
            rejected_at=rejected_at,
        )
        session.add(invitation)
        await session.commit()
        return invitation.id, token


def _signup_payload() -> dict[str, object]:
    return {
        "full_name": "New Invitation User",
        "password": "ValidPass123!",
        "password_confirmation": "ValidPass123!",
        "phone_number": "+905551112233",
        "whatsapp_opt_in": True,
        "locale": "tr",
    }


async def _create_existing_user(
    ctx: InviteContext,
    *,
    email: str,
    user_type: str,
) -> User:
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            password_hash="not-a-real-hash-test-fixture-only",
            full_name="Existing Recipient",
            user_type=user_type,
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        ctx.user_ids.append(user.id)
        return user


class TestInvitationPreview:
    async def test_pending_preview_discloses_only_safe_target_and_account_state(
        self, client: AsyncClient, invite_context: InviteContext
    ) -> None:
        email = f"preview-{uuid.uuid4().hex[:8]}@test.local"
        await _create_existing_user(
            invite_context, email=email, user_type=UserType.BRAND_USER.value
        )
        _, token = await _create_invitation(
            invite_context,
            invitation_type="brand",
            email=email,
            role=BrandMemberRole.BRAND_MANAGER.value,
        )

        response = await client.get(f"/api/v1/invitations/preview/{token}")

        assert response.status_code == 200
        body = response.json()
        assert body["state"] == "pending"
        assert body["account_exists"] is True
        assert body["account_type_compatible"] is True
        assert body["email"] == email
        assert "id" not in body
        assert "agency_id" not in body
        assert "brand_id" not in body

    @pytest.mark.parametrize(
        ("state", "kwargs"),
        [
            ("expired", {"expires_at": datetime.now(UTC) - timedelta(minutes=1)}),
            ("revoked", {"revoked_at": datetime.now(UTC)}),
            ("declined", {"rejected_at": datetime.now(UTC)}),
        ],
    )
    async def test_terminal_preview_does_not_disclose_account_state(
        self,
        client: AsyncClient,
        invite_context: InviteContext,
        state: str,
        kwargs: dict[str, datetime],
    ) -> None:
        _, token = await _create_invitation(
            invite_context,
            invitation_type="agency",
            email=f"terminal-{uuid.uuid4().hex[:8]}@test.local",
            role=AgencyMemberRole.ADMIN.value,
            **kwargs,
        )

        response = await client.get(f"/api/v1/invitations/preview/{token}")

        assert response.status_code == 200
        assert response.json()["state"] == state
        assert response.json()["account_exists"] is None


class TestInvitationSignup:
    async def test_brand_invite_creates_verified_brand_user_member_and_session(
        self, client: AsyncClient, invite_context: InviteContext
    ) -> None:
        email = f"new-brand-{uuid.uuid4().hex[:8]}@test.local"
        invitation_id, token = await _create_invitation(
            invite_context,
            invitation_type="brand",
            email=email,
            role=BrandMemberRole.EXTERNAL_APPROVER.value,
        )

        response = await client.post(f"/api/v1/invitations/signup/{token}", json=_signup_payload())

        assert response.status_code == 201
        assert response.json()["redirect_to"] == "/brand/dashboard"
        assert response.cookies.get("refresh_token")
        async with AsyncSessionLocal() as session:
            user = await session.scalar(select(User).where(User.email == email))
            assert user is not None
            invite_context.user_ids.append(user.id)
            assert user.user_type == UserType.BRAND_USER.value
            assert user.is_verified is True
            assert user.locale == "tr"
            member = await session.scalar(
                select(BrandMember).where(
                    BrandMember.brand_id == invite_context.brand_id,
                    BrandMember.user_id == user.id,
                )
            )
            assert member is not None
            assert member.role == BrandMemberRole.EXTERNAL_APPROVER.value
            assert member.status == BrandMemberStatus.ACTIVE.value
            assert member.joined_at is not None
            invitation = await session.get(Invitation, invitation_id)
            assert invitation is not None and invitation.accepted_at is not None
            activity = await session.scalar(
                select(ActivityLog).where(
                    ActivityLog.entity_id == invitation_id,
                    ActivityLog.action == "invitation.accepted",
                )
            )
            assert activity is not None

    async def test_agency_invite_joins_existing_agency_without_creating_another(
        self, client: AsyncClient, invite_context: InviteContext
    ) -> None:
        email = f"new-agency-{uuid.uuid4().hex[:8]}@test.local"
        _, token = await _create_invitation(
            invite_context,
            invitation_type="agency",
            email=email,
            role=AgencyMemberRole.DESIGNER.value,
        )
        async with AsyncSessionLocal() as session:
            before = await session.scalar(select(func.count(Agency.id)))

        response = await client.post(f"/api/v1/invitations/signup/{token}", json=_signup_payload())

        assert response.status_code == 201
        assert response.json()["redirect_to"] == "/dashboard"
        async with AsyncSessionLocal() as session:
            after = await session.scalar(select(func.count(Agency.id)))
            assert after == before
            user = await session.scalar(select(User).where(User.email == email))
            assert user is not None
            invite_context.user_ids.append(user.id)
            assert user.user_type == UserType.AGENCY_USER.value
            member = await session.scalar(
                select(AgencyMember).where(
                    AgencyMember.agency_id == invite_context.agency_id,
                    AgencyMember.user_id == user.id,
                )
            )
            assert member is not None and member.role == AgencyMemberRole.DESIGNER.value

    async def test_duplicate_signup_creates_no_duplicate_user_or_membership(
        self, client: AsyncClient, invite_context: InviteContext
    ) -> None:
        email = f"duplicate-{uuid.uuid4().hex[:8]}@test.local"
        _, token = await _create_invitation(
            invite_context,
            invitation_type="brand",
            email=email,
            role=BrandMemberRole.BRAND_VIEWER.value,
        )

        first = await client.post(f"/api/v1/invitations/signup/{token}", json=_signup_payload())
        second = await client.post(f"/api/v1/invitations/signup/{token}", json=_signup_payload())

        assert first.status_code == 201
        assert second.status_code == 409
        async with AsyncSessionLocal() as session:
            users = await session.scalar(select(func.count(User.id)).where(User.email == email))
            user = await session.scalar(select(User).where(User.email == email))
            assert user is not None
            invite_context.user_ids.append(user.id)
            members = await session.scalar(
                select(func.count(BrandMember.id)).where(
                    BrandMember.brand_id == invite_context.brand_id,
                    BrandMember.user_id == user.id,
                )
            )
            assert users == 1
            assert members == 1

    async def test_existing_account_cannot_use_signup_endpoint(
        self, client: AsyncClient, invite_context: InviteContext
    ) -> None:
        email = f"existing-signup-{uuid.uuid4().hex[:8]}@test.local"
        await _create_existing_user(
            invite_context, email=email, user_type=UserType.BRAND_USER.value
        )
        invitation_id, token = await _create_invitation(
            invite_context,
            invitation_type="brand",
            email=email,
            role=BrandMemberRole.BRAND_OWNER.value,
        )

        response = await client.post(f"/api/v1/invitations/signup/{token}", json=_signup_payload())

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "INVITATION_ACCOUNT_EXISTS"
        async with AsyncSessionLocal() as session:
            invitation = await session.get(Invitation, invitation_id)
            assert invitation is not None and invitation.accepted_at is None

    async def test_limit_failure_rolls_back_user_and_preserves_invitation(
        self, client: AsyncClient, invite_context: InviteContext
    ) -> None:
        existing_email = f"seat-{uuid.uuid4().hex[:8]}@test.local"
        existing = await _create_existing_user(
            invite_context,
            email=existing_email,
            user_type=UserType.BRAND_USER.value,
        )
        async with AsyncSessionLocal() as session:
            plan = await session.get(Plan, invite_context.plan_id)
            assert plan is not None
            plan.max_brand_users = 1
            session.add(
                BrandMember(
                    brand_id=invite_context.brand_id,
                    user_id=existing.id,
                    role=BrandMemberRole.BRAND_VIEWER.value,
                    status=BrandMemberStatus.ACTIVE.value,
                    joined_at=datetime.now(UTC),
                )
            )
            await session.commit()

        email = f"over-limit-{uuid.uuid4().hex[:8]}@test.local"
        invitation_id, token = await _create_invitation(
            invite_context,
            invitation_type="brand",
            email=email,
            role=BrandMemberRole.BRAND_VIEWER.value,
        )

        response = await client.post(f"/api/v1/invitations/signup/{token}", json=_signup_payload())

        assert response.status_code == 403
        async with AsyncSessionLocal() as session:
            assert await session.scalar(select(User).where(User.email == email)) is None
            invitation = await session.get(Invitation, invitation_id)
            assert invitation is not None and invitation.accepted_at is None


class TestExistingInvitationRecipient:
    async def test_compatible_existing_brand_user_accepts(
        self, client: AsyncClient, invite_context: InviteContext
    ) -> None:
        email = f"compatible-{uuid.uuid4().hex[:8]}@test.local"
        user = await _create_existing_user(
            invite_context, email=email, user_type=UserType.BRAND_USER.value
        )
        _, token = await _create_invitation(
            invite_context,
            invitation_type="brand",
            email=email,
            role=BrandMemberRole.BRAND_MANAGER.value,
        )
        access = create_access_token(
            str(user.id), extra_claims={"user_type": UserType.BRAND_USER.value}
        )

        response = await client.post(
            f"/api/v1/invitations/accept/{token}",
            headers={"Authorization": f"Bearer {access}"},
        )

        assert response.status_code == 204
        async with AsyncSessionLocal() as session:
            member = await session.scalar(
                select(BrandMember).where(
                    BrandMember.brand_id == invite_context.brand_id,
                    BrandMember.user_id == user.id,
                )
            )
            assert member is not None and member.role == BrandMemberRole.BRAND_MANAGER.value

    async def test_wrong_logged_in_account_is_rejected_and_invitation_preserved(
        self, client: AsyncClient, invite_context: InviteContext
    ) -> None:
        invited_email = f"right-{uuid.uuid4().hex[:8]}@test.local"
        wrong = await _create_existing_user(
            invite_context,
            email=f"wrong-{uuid.uuid4().hex[:8]}@test.local",
            user_type=UserType.BRAND_USER.value,
        )
        invitation_id, token = await _create_invitation(
            invite_context,
            invitation_type="brand",
            email=invited_email,
            role=BrandMemberRole.BRAND_VIEWER.value,
        )
        access = create_access_token(
            str(wrong.id), extra_claims={"user_type": UserType.BRAND_USER.value}
        )

        response = await client.post(
            f"/api/v1/invitations/accept/{token}",
            headers={"Authorization": f"Bearer {access}"},
        )

        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "INVITATION_EMAIL_MISMATCH"
        async with AsyncSessionLocal() as session:
            invitation = await session.get(Invitation, invitation_id)
            assert invitation is not None and invitation.accepted_at is None

    async def test_incompatible_existing_user_is_rejected_without_conversion(
        self, client: AsyncClient, invite_context: InviteContext
    ) -> None:
        email = f"incompatible-{uuid.uuid4().hex[:8]}@test.local"
        user = await _create_existing_user(
            invite_context, email=email, user_type=UserType.AGENCY_USER.value
        )
        invitation_id, token = await _create_invitation(
            invite_context,
            invitation_type="brand",
            email=email,
            role=BrandMemberRole.BRAND_OWNER.value,
        )
        access = create_access_token(
            str(user.id), extra_claims={"user_type": UserType.AGENCY_USER.value}
        )

        response = await client.post(
            f"/api/v1/invitations/accept/{token}",
            headers={"Authorization": f"Bearer {access}"},
        )

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "INVITATION_ACCOUNT_TYPE_CONFLICT"
        async with AsyncSessionLocal() as session:
            persisted_user = await session.get(User, user.id)
            invitation = await session.get(Invitation, invitation_id)
            assert persisted_user is not None
            assert persisted_user.user_type == UserType.AGENCY_USER.value
            assert invitation is not None and invitation.accepted_at is None

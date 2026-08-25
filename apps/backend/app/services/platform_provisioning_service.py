"""Auditable Platform Admin provisioning and membership recovery operations."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import ActivityLog
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.brand import Brand
from app.models.brand_member import BrandMember
from app.models.enums import (
    AgencyMemberRole,
    AgencyMemberStatus,
    BillingProvider,
    BrandMemberRole,
    BrandMemberStatus,
    UserType,
)
from app.models.invitation import Invitation
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.repositories.agency import AgencyRepository
from app.repositories.agency_member import AgencyMemberRepository
from app.repositories.brand import BrandRepository
from app.repositories.brand_member import BrandMemberRepository
from app.repositories.invitation import InvitationRepository
from app.repositories.platform_audit_log import PlatformAuditLogRepository
from app.repositories.user import UserRepository
from app.schemas.platform import (
    PlatformAgencyCreateRequest,
    PlatformBrandCreateRequest,
    PlatformMemberAttachRequest,
    PlatformMemberInviteRequest,
)
from app.services.entitlement_service import EntitlementService
from app.services.invitation_service import InvitationService
from app.services.token_service import generate_token, hash_token

_CONFLICT = status.HTTP_409_CONFLICT
_NOT_FOUND = status.HTTP_404_NOT_FOUND
_INVITE_DAYS = 7


@dataclass
class AgencyProvisioningResult:
    agency: Agency
    owner_action: str
    owner_email: str | None
    invitation: Invitation | None = None


@dataclass
class BrandProvisioningResult:
    brand: Brand
    contact_action: str
    contact_email: str | None
    invitation: Invitation | None = None


def _slug(name: str, kind: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80] or kind
    return f"{base}-{uuid.uuid4().hex[:8]}"


class PlatformProvisioningService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.agencies = AgencyRepository(db)
        self.agency_members = AgencyMemberRepository(db)
        self.brands = BrandRepository(db)
        self.brand_members = BrandMemberRepository(db)
        self.invitations = InvitationRepository(db)
        self.users = UserRepository(db)
        self.audit = PlatformAuditLogRepository(db)
        self.entitlements = EntitlementService(db)

    @staticmethod
    def _error(code: str, message: str, status_code: int = _CONFLICT) -> HTTPException:
        return HTTPException(status_code=status_code, detail={"code": code, "message": message})

    async def _get_plan(self, plan_id: uuid.UUID) -> Plan:
        plan = await self.db.scalar(
            select(Plan).where(
                Plan.id == plan_id,
                Plan.deleted_at.is_(None),
                Plan.is_active.is_(True),
            )
        )
        if plan is None:
            raise self._error("PLAN_NOT_FOUND", "Plan bulunamadı", _NOT_FOUND)
        return plan

    async def _get_agency(self, agency_id: uuid.UUID, *, lock: bool = False) -> Agency:
        stmt = select(Agency).where(
            Agency.id == agency_id,
            Agency.deleted_at.is_(None),
            Agency.is_demo.is_(False),
        )
        if lock:
            stmt = stmt.with_for_update()
        agency = await self.db.scalar(stmt)
        if agency is None:
            raise self._error("AGENCY_NOT_FOUND", "Ajans bulunamadı", _NOT_FOUND)
        return agency

    async def _get_brand(self, brand_id: uuid.UUID, *, lock: bool = False) -> Brand:
        stmt = (
            select(Brand)
            .join(Agency, Agency.id == Brand.agency_id)
            .where(
                Brand.id == brand_id,
                Brand.deleted_at.is_(None),
                Agency.deleted_at.is_(None),
                Agency.is_demo.is_(False),
            )
        )
        if lock:
            stmt = stmt.with_for_update()
        brand = await self.db.scalar(stmt)
        if brand is None:
            raise self._error("BRAND_NOT_FOUND", "Marka bulunamadı", _NOT_FOUND)
        return brand

    async def _compatible_user(self, email: str, expected_type: str) -> User:
        user = await self.users.get_by_email(email)
        if user is None:
            raise self._error("USER_NOT_FOUND", "Bu e-posta ile mevcut kullanıcı bulunamadı")
        if user.user_type != expected_type:
            raise self._error(
                "USER_TYPE_CONFLICT",
                "Kullanıcı farklı bir portal türüne ait. Hesap türü değiştirilmedi.",
            )
        if not user.is_active:
            raise self._error("USER_INACTIVE", "Devre dışı kullanıcı bağlanamaz")
        return user

    async def _create_invitation(
        self,
        *,
        agency_id: uuid.UUID,
        brand_id: uuid.UUID | None,
        invitation_type: str,
        email: str,
        role: str,
        admin: User,
    ) -> tuple[Invitation, str]:
        if invitation_type == "agency":
            await self.entitlements.check_user_limit(agency_id, lock=True)
            await self.entitlements.check_pending_invite_limit(agency_id, lock=True)
        else:
            assert brand_id is not None
            await self.entitlements.check_brand_user_limit(agency_id, brand_id, lock=True)
            await self.entitlements.check_pending_invite_limit(agency_id, brand_id, lock=True)

        # The tenant row lock above serializes same-target writes. Re-check only
        # after acquiring it so concurrent double submissions cannot create two
        # pending invitations for the same recipient and target.
        existing_user = await self.users.get_by_email(email)
        if existing_user is not None:
            raise self._error(
                "USER_ALREADY_EXISTS",
                "Bu e-posta için hesap mevcut. Açık onayla mevcut kullanıcıyı bağlayın.",
            )

        existing_invite = await self.invitations.get_pending_for_email_and_agency(
            email, agency_id, invitation_type
        )
        if existing_invite is not None and (
            invitation_type == "agency" or existing_invite.brand_id == brand_id
        ):
            raise self._error("INVITATION_EXISTS", "Bu e-posta için bekleyen davet zaten var")

        plaintext = generate_token(48)
        invitation = await self.invitations.create(
            agency_id=agency_id,
            brand_id=brand_id,
            invitation_type=invitation_type,
            email=email.lower(),
            role=role,
            token_hash=hash_token(plaintext),
            invited_by=admin.id,
            expires_at=datetime.now(UTC) + timedelta(days=_INVITE_DAYS),
        )
        return invitation, plaintext

    async def _audit(
        self,
        *,
        admin: User,
        action: str,
        target_type: str,
        target_id: uuid.UUID,
        agency_id: uuid.UUID | None,
        ip: str | None,
        user_agent: str | None,
        meta: dict | None = None,
    ) -> None:
        await self.audit.create(
            admin_user_id=admin.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_tenant_type="agency" if agency_id else None,
            target_tenant_id=agency_id,
            ip_address=ip,
            user_agent=user_agent,
            meta=meta,
        )

    async def create_agency(
        self,
        data: PlatformAgencyCreateRequest,
        *,
        admin: User,
        ip: str | None,
        user_agent: str | None,
    ) -> AgencyProvisioningResult:
        plan = await self._get_plan(data.plan_id)
        owner_email = str(data.owner_email).lower() if data.owner_email else None
        agency = Agency(
            name=data.name.strip(),
            slug=_slug(data.name, "agency"),
            status=data.status,
            plan_id=plan.id,
            owner_user_id=None,
            is_demo=False,
        )
        self.db.add(agency)
        await self.db.flush()
        self.db.add(
            Subscription(
                agency_id=agency.id,
                plan_id=plan.id,
                status="active",
                billing_provider=BillingProvider.MANUAL.value,
            )
        )
        await self.db.flush()

        owner_action = "none"
        invitation: Invitation | None = None
        plaintext: str | None = None
        if data.owner_mode == "invite":
            assert owner_email is not None
            invitation, plaintext = await self._create_invitation(
                agency_id=agency.id,
                brand_id=None,
                invitation_type="agency",
                email=owner_email,
                role=AgencyMemberRole.OWNER.value,
                admin=admin,
            )
            owner_action = "invited"
        elif data.owner_mode == "attach":
            assert owner_email is not None
            owner = await self._compatible_user(owner_email, UserType.AGENCY_USER.value)
            await self.entitlements.check_user_limit(agency.id, lock=True)
            await self.agency_members.create(
                agency_id=agency.id,
                user_id=owner.id,
                role=AgencyMemberRole.OWNER.value,
                status=AgencyMemberStatus.ACTIVE.value,
                joined_at=datetime.now(UTC),
            )
            agency.owner_user_id = owner.id
            self.db.add(agency)
            owner_action = "attached"

        await self._audit(
            admin=admin,
            action="agency.created_by_platform",
            target_type="agency",
            target_id=agency.id,
            agency_id=agency.id,
            ip=ip,
            user_agent=user_agent,
            meta={
                "name": agency.name,
                "slug": agency.slug,
                "status": agency.status,
                "plan_id": str(plan.id),
                "billing_provider": BillingProvider.MANUAL.value,
                "owner_mode": data.owner_mode,
            },
        )
        if owner_action != "none":
            await self._audit(
                admin=admin,
                action=(
                    "agency.owner_invited_by_platform"
                    if owner_action == "invited"
                    else "agency.user_attached_by_platform"
                ),
                target_type="agency",
                target_id=agency.id,
                agency_id=agency.id,
                ip=ip,
                user_agent=user_agent,
                meta={"user_email": owner_email, "role": AgencyMemberRole.OWNER.value},
            )
        self.db.add(
            ActivityLog(
                agency_id=agency.id,
                actor_user_id=admin.id,
                action="agency.created_by_platform",
                entity_type="agency",
                entity_id=agency.id,
                meta={"owner_action": owner_action},
            )
        )

        try:
            await self.db.commit()
            await self.db.refresh(agency)
        except IntegrityError as exc:
            await self.db.rollback()
            raise self._error(
                "AGENCY_CREATE_CONFLICT",
                "Ajans eş zamanlı bir işlemle çakıştı. Lütfen tekrar deneyin.",
            ) from exc

        if invitation is not None and plaintext is not None:
            await InvitationService(self.db).send_invitation_email(
                invitation,
                plaintext,
                inviter_name=admin.full_name,
                locale=data.locale,
            )
        return AgencyProvisioningResult(
            agency=agency,
            owner_action=owner_action,
            owner_email=owner_email,
            invitation=invitation,
        )

    async def create_brand(
        self,
        data: PlatformBrandCreateRequest,
        *,
        admin: User,
        ip: str | None,
        user_agent: str | None,
    ) -> BrandProvisioningResult:
        agency = await self._get_agency(data.agency_id, lock=True)
        await self.entitlements.check_brand_limit(agency.id, lock=True)
        contact_email = str(data.contact_email).lower() if data.contact_email else None
        brand = Brand(
            agency_id=agency.id,
            name=data.name.strip(),
            slug=_slug(data.name, "brand"),
            status=data.status,
            default_language=data.default_language,
            contact_email=contact_email,
        )
        self.db.add(brand)
        await self.db.flush()

        contact_action = "none"
        invitation: Invitation | None = None
        plaintext: str | None = None
        if data.contact_mode == "invite":
            assert contact_email is not None
            invitation, plaintext = await self._create_invitation(
                agency_id=agency.id,
                brand_id=brand.id,
                invitation_type="brand",
                email=contact_email,
                role=data.contact_role,
                admin=admin,
            )
            contact_action = "invited"
        elif data.contact_mode == "attach":
            assert contact_email is not None
            contact = await self._compatible_user(contact_email, UserType.BRAND_USER.value)
            await self.entitlements.check_brand_user_limit(agency.id, brand.id, lock=True)
            await self.brand_members.create(
                brand_id=brand.id,
                user_id=contact.id,
                role=data.contact_role,
                status=BrandMemberStatus.ACTIVE.value,
                joined_at=datetime.now(UTC),
            )
            contact_action = "attached"

        await self._audit(
            admin=admin,
            action="brand.created_by_platform",
            target_type="brand",
            target_id=brand.id,
            agency_id=agency.id,
            ip=ip,
            user_agent=user_agent,
            meta={
                "name": brand.name,
                "slug": brand.slug,
                "status": brand.status,
                "default_language": brand.default_language,
                "contact_mode": data.contact_mode,
            },
        )
        if contact_action != "none":
            await self._audit(
                admin=admin,
                action=(
                    "brand.user_invited_by_platform"
                    if contact_action == "invited"
                    else "brand.user_attached_by_platform"
                ),
                target_type="brand",
                target_id=brand.id,
                agency_id=agency.id,
                ip=ip,
                user_agent=user_agent,
                meta={"user_email": contact_email, "role": data.contact_role},
            )
        self.db.add(
            ActivityLog(
                agency_id=agency.id,
                brand_id=brand.id,
                actor_user_id=admin.id,
                action="brand.created_by_platform",
                entity_type="brand",
                entity_id=brand.id,
                meta={"contact_action": contact_action},
            )
        )

        try:
            await self.db.commit()
            await self.db.refresh(brand)
        except IntegrityError as exc:
            await self.db.rollback()
            raise self._error(
                "BRAND_CREATE_CONFLICT",
                "Marka eş zamanlı bir işlemle çakıştı. Lütfen tekrar deneyin.",
            ) from exc

        if invitation is not None and plaintext is not None:
            await InvitationService(self.db).send_invitation_email(
                invitation,
                plaintext,
                inviter_name=admin.full_name,
                locale=data.default_language,
            )
        return BrandProvisioningResult(
            brand=brand,
            contact_action=contact_action,
            contact_email=contact_email,
            invitation=invitation,
        )

    async def invite_agency_member(
        self,
        agency_id: uuid.UUID,
        data: PlatformMemberInviteRequest,
        *,
        admin: User,
        ip: str | None,
        user_agent: str | None,
    ) -> Invitation:
        agency = await self._get_agency(agency_id, lock=True)
        if data.role not in {role.value for role in AgencyMemberRole}:
            raise self._error(
                "INVALID_ROLE",
                "Geçersiz ajans rolü",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        invitation, plaintext = await self._create_invitation(
            agency_id=agency.id,
            brand_id=None,
            invitation_type="agency",
            email=str(data.email).lower(),
            role=data.role,
            admin=admin,
        )
        await self._audit(
            admin=admin,
            action="agency.user_invited_by_platform",
            target_type="invitation",
            target_id=invitation.id,
            agency_id=agency.id,
            ip=ip,
            user_agent=user_agent,
            meta={"user_email": invitation.email, "role": invitation.role},
        )
        await self.db.commit()
        await InvitationService(self.db).send_invitation_email(
            invitation,
            plaintext,
            inviter_name=admin.full_name,
            locale=data.locale,
        )
        return invitation

    async def invite_brand_member(
        self,
        brand_id: uuid.UUID,
        data: PlatformMemberInviteRequest,
        *,
        admin: User,
        ip: str | None,
        user_agent: str | None,
    ) -> Invitation:
        brand = await self._get_brand(brand_id, lock=True)
        assert brand.agency_id is not None
        if data.role not in {role.value for role in BrandMemberRole}:
            raise self._error(
                "INVALID_ROLE",
                "Geçersiz marka rolü",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        invitation, plaintext = await self._create_invitation(
            agency_id=brand.agency_id,
            brand_id=brand.id,
            invitation_type="brand",
            email=str(data.email).lower(),
            role=data.role,
            admin=admin,
        )
        await self._audit(
            admin=admin,
            action="brand.user_invited_by_platform",
            target_type="invitation",
            target_id=invitation.id,
            agency_id=brand.agency_id,
            ip=ip,
            user_agent=user_agent,
            meta={
                "user_email": invitation.email,
                "role": invitation.role,
                "brand_id": str(brand.id),
            },
        )
        await self.db.commit()
        await InvitationService(self.db).send_invitation_email(
            invitation,
            plaintext,
            inviter_name=admin.full_name,
            locale=data.locale,
        )
        return invitation

    async def attach_agency_member(
        self,
        agency_id: uuid.UUID,
        data: PlatformMemberAttachRequest,
        *,
        admin: User,
        ip: str | None,
        user_agent: str | None,
    ) -> AgencyMember:
        agency = await self._get_agency(agency_id, lock=True)
        if data.role not in {role.value for role in AgencyMemberRole}:
            raise self._error(
                "INVALID_ROLE",
                "Geçersiz ajans rolü",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        user = await self._compatible_user(str(data.email).lower(), UserType.AGENCY_USER.value)
        if await self.agency_members.get_membership(agency.id, user.id) is not None:
            raise self._error("MEMBERSHIP_EXISTS", "Kullanıcı zaten bu ajansa bağlı")
        await self.entitlements.check_user_limit(agency.id, lock=True)
        member = await self.agency_members.create(
            agency_id=agency.id,
            user_id=user.id,
            role=data.role,
            status=AgencyMemberStatus.ACTIVE.value,
            joined_at=datetime.now(UTC),
        )
        if data.role == AgencyMemberRole.OWNER.value and agency.owner_user_id is None:
            agency.owner_user_id = user.id
            self.db.add(agency)
        await self._audit(
            admin=admin,
            action="agency.user_attached_by_platform",
            target_type="agency_member",
            target_id=member.id,
            agency_id=agency.id,
            ip=ip,
            user_agent=user_agent,
            meta={"user_email": user.email, "role": data.role},
        )
        await self.db.commit()
        return member

    async def attach_brand_member(
        self,
        brand_id: uuid.UUID,
        data: PlatformMemberAttachRequest,
        *,
        admin: User,
        ip: str | None,
        user_agent: str | None,
    ) -> BrandMember:
        brand = await self._get_brand(brand_id, lock=True)
        assert brand.agency_id is not None
        if data.role not in {role.value for role in BrandMemberRole}:
            raise self._error(
                "INVALID_ROLE",
                "Geçersiz marka rolü",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        user = await self._compatible_user(str(data.email).lower(), UserType.BRAND_USER.value)
        if await self.brand_members.get_membership(brand.id, user.id) is not None:
            raise self._error("MEMBERSHIP_EXISTS", "Kullanıcı zaten bu markaya bağlı")
        await self.entitlements.check_brand_user_limit(brand.agency_id, brand.id, lock=True)
        member = await self.brand_members.create(
            brand_id=brand.id,
            user_id=user.id,
            role=data.role,
            status=BrandMemberStatus.ACTIVE.value,
            joined_at=datetime.now(UTC),
        )
        await self._audit(
            admin=admin,
            action="brand.user_attached_by_platform",
            target_type="brand_member",
            target_id=member.id,
            agency_id=brand.agency_id,
            ip=ip,
            user_agent=user_agent,
            meta={"user_email": user.email, "role": data.role, "brand_id": str(brand.id)},
        )
        await self.db.commit()
        return member

    async def scoped_invitation(
        self,
        invitation_id: uuid.UUID,
        *,
        agency_id: uuid.UUID | None = None,
        brand_id: uuid.UUID | None = None,
        lock: bool = False,
    ) -> Invitation:
        if agency_id is not None:
            await self._get_agency(agency_id)
        if brand_id is not None:
            await self._get_brand(brand_id)
        stmt = select(Invitation).where(
            Invitation.id == invitation_id,
            Invitation.deleted_at.is_(None),
        )
        if agency_id is not None:
            stmt = stmt.where(
                Invitation.agency_id == agency_id,
                Invitation.invitation_type == "agency",
            )
        if brand_id is not None:
            stmt = stmt.where(
                Invitation.brand_id == brand_id,
                Invitation.invitation_type == "brand",
            )
        if lock:
            stmt = stmt.with_for_update()
        invitation = await self.db.scalar(stmt)
        if invitation is None:
            raise self._error("INVITATION_NOT_FOUND", "Davet bulunamadı", _NOT_FOUND)
        return invitation

    async def resend_invitation(
        self,
        invitation: Invitation,
        *,
        admin: User,
        ip: str | None,
        user_agent: str | None,
    ) -> Invitation:
        if not invitation.is_pending:
            raise self._error(
                "INVITATION_NOT_PENDING",
                "Yalnızca bekleyen davet yeniden gönderilebilir",
            )
        plaintext = generate_token(48)
        invitation.token_hash = hash_token(plaintext)
        invitation.expires_at = datetime.now(UTC) + timedelta(days=_INVITE_DAYS)
        invitation.resent_count += 1
        self.db.add(invitation)
        await self._audit(
            admin=admin,
            action="invitation.resent_by_platform",
            target_type="invitation",
            target_id=invitation.id,
            agency_id=invitation.agency_id,
            ip=ip,
            user_agent=user_agent,
            meta={"user_email": invitation.email, "role": invitation.role},
        )
        await self.db.commit()
        await self.db.refresh(invitation)
        await InvitationService(self.db).send_invitation_email(
            invitation,
            plaintext,
            inviter_name=admin.full_name,
        )
        return invitation

    async def revoke_invitation(
        self,
        invitation: Invitation,
        *,
        admin: User,
        ip: str | None,
        user_agent: str | None,
    ) -> None:
        if not invitation.is_pending:
            raise self._error("INVITATION_NOT_PENDING", "Yalnızca bekleyen davet iptal edilebilir")
        invitation.revoked_at = datetime.now(UTC)
        self.db.add(invitation)
        await self._audit(
            admin=admin,
            action="invitation.revoked_by_platform",
            target_type="invitation",
            target_id=invitation.id,
            agency_id=invitation.agency_id,
            ip=ip,
            user_agent=user_agent,
            meta={"user_email": invitation.email, "role": invitation.role},
        )
        await self.db.commit()

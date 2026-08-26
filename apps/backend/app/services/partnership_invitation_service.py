from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import ActivityLog
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.brand import Brand
from app.models.brand_member import BrandMember
from app.models.enums import (
    AgencyMemberRole,
    AgencyMemberStatus,
    AgencyStatus,
    BrandMemberRole,
    BrandMemberStatus,
    BrandStatus,
    UserType,
)
from app.models.partnership_invitation import PartnershipInvitation
from app.models.user import User
from app.repositories.agency import AgencyRepository
from app.repositories.brand import BrandRepository
from app.schemas.partnership_invitation import (
    PartnershipAcceptResponse,
    PartnershipInvitationPreview,
    PartnershipInviteCreate,
)
from app.services import email_service
from app.services.token_service import generate_token, hash_token

AGENCY_INVITES_BRAND = "agency_invites_brand"
BRAND_INVITES_AGENCY = "brand_invites_agency"
_INVITE_DAYS = 7


class PartnershipInvitationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _error(code: str, message: str, status_code: int = 409) -> HTTPException:
        return HTTPException(status_code=status_code, detail={"code": code, "message": message})

    @staticmethod
    def state(invitation: PartnershipInvitation) -> str:
        if invitation.accepted_at is not None:
            return "accepted"
        if invitation.revoked_at is not None:
            return "revoked"
        if invitation.is_pending:
            return "pending"
        return "expired"

    async def _pending_duplicate(
        self,
        *,
        direction: str,
        email: str,
        agency_id: uuid.UUID | None,
        brand_id: uuid.UUID | None,
    ) -> PartnershipInvitation | None:
        return await self.db.scalar(
            select(PartnershipInvitation).where(
                PartnershipInvitation.direction == direction,
                PartnershipInvitation.email == email.lower(),
                PartnershipInvitation.agency_id == agency_id,
                PartnershipInvitation.brand_id == brand_id,
                PartnershipInvitation.accepted_at.is_(None),
                PartnershipInvitation.revoked_at.is_(None),
                PartnershipInvitation.deleted_at.is_(None),
                PartnershipInvitation.expires_at > datetime.now(UTC),
            )
        )

    async def create_from_agency(
        self,
        agency: Agency,
        actor_member: AgencyMember,
        actor: User,
        data: PartnershipInviteCreate,
    ) -> PartnershipInvitation:
        if agency.is_demo:
            raise self._error("DEMO_PARTNERSHIP_DISABLED", "Demo ortamında davet gönderilemez", 403)
        if actor_member.role not in {AgencyMemberRole.OWNER.value, AgencyMemberRole.ADMIN.value}:
            raise self._error("PARTNERSHIP_FORBIDDEN", "İş ortaklığı daveti yetkiniz yok", 403)
        await self.db.execute(select(Agency.id).where(Agency.id == agency.id).with_for_update())
        if await self._pending_duplicate(
            direction=AGENCY_INVITES_BRAND,
            email=str(data.email),
            agency_id=agency.id,
            brand_id=None,
        ):
            raise self._error("PARTNERSHIP_INVITATION_EXISTS", "Bu e-posta için bekleyen davet var")
        return await self._create_and_send(
            direction=AGENCY_INVITES_BRAND,
            agency_id=agency.id,
            brand_id=None,
            email=str(data.email),
            actor=actor,
            source_name=agency.name,
            message=data.message,
        )

    async def create_from_brand(
        self,
        brand: Brand,
        actor_member: BrandMember,
        actor: User,
        data: PartnershipInviteCreate,
    ) -> PartnershipInvitation:
        if actor_member.role != BrandMemberRole.BRAND_OWNER.value:
            raise self._error(
                "PARTNERSHIP_FORBIDDEN",
                "Ajans iş ortaklığı davetini yalnızca marka sahibi gönderebilir",
                403,
            )
        if brand.agency_id is not None:
            raise self._error(
                "BRAND_ALREADY_CONNECTED",
                "Bu marka zaten bir ajansla bağlantılı",
            )
        await self.db.execute(select(Brand.id).where(Brand.id == brand.id).with_for_update())
        if await self._pending_duplicate(
            direction=BRAND_INVITES_AGENCY,
            email=str(data.email),
            agency_id=None,
            brand_id=brand.id,
        ):
            raise self._error("PARTNERSHIP_INVITATION_EXISTS", "Bu e-posta için bekleyen davet var")
        return await self._create_and_send(
            direction=BRAND_INVITES_AGENCY,
            agency_id=None,
            brand_id=brand.id,
            email=str(data.email),
            actor=actor,
            source_name=brand.name,
            message=data.message,
        )

    async def _create_and_send(
        self,
        *,
        direction: str,
        agency_id: uuid.UUID | None,
        brand_id: uuid.UUID | None,
        email: str,
        actor: User,
        source_name: str,
        message: str | None,
    ) -> PartnershipInvitation:
        plaintext = generate_token(48)
        invitation = PartnershipInvitation(
            direction=direction,
            agency_id=agency_id,
            brand_id=brand_id,
            email=email.lower(),
            token_hash=hash_token(plaintext),
            invited_by=actor.id,
            expires_at=datetime.now(UTC) + timedelta(days=_INVITE_DAYS),
        )
        self.db.add(invitation)
        await self.db.commit()
        await self.db.refresh(invitation)
        await email_service.send_partnership_invite_email(
            self.db,
            to_email=email,
            source_name=source_name,
            inviter_name=actor.full_name,
            direction=direction,
            token=plaintext,
            message=message,
            locale=actor.locale,
        )
        return invitation

    async def get_by_token(self, token: str, *, lock: bool = False) -> PartnershipInvitation:
        stmt = select(PartnershipInvitation).where(
            PartnershipInvitation.token_hash == hash_token(token),
            PartnershipInvitation.deleted_at.is_(None),
        )
        if lock:
            stmt = stmt.with_for_update()
        invitation = await self.db.scalar(stmt)
        if invitation is None:
            raise self._error("PARTNERSHIP_INVITATION_NOT_FOUND", "Davet bulunamadı", 404)
        return invitation

    async def preview(self, token: str) -> PartnershipInvitationPreview:
        invitation = await self.get_by_token(token)
        if invitation.direction == AGENCY_INVITES_BRAND:
            assert invitation.agency_id is not None
            source = await self.db.scalar(
                select(Agency).where(
                    Agency.id == invitation.agency_id,
                    Agency.deleted_at.is_(None),
                )
            )
            required_type = "brand"
        else:
            assert invitation.brand_id is not None
            source = await self.db.scalar(
                select(Brand).where(
                    Brand.id == invitation.brand_id,
                    Brand.deleted_at.is_(None),
                )
            )
            required_type = "agency"
        if source is None:
            raise self._error("PARTNERSHIP_SOURCE_MISSING", "Davet kaynağı artık mevcut değil", 410)
        return PartnershipInvitationPreview(
            direction=invitation.direction,
            source_name=source.name,
            email=invitation.email,
            expires_at=invitation.expires_at,
            state=self.state(invitation),
            required_workspace_type=required_type,
        )

    async def accept(
        self,
        token: str,
        target_workspace_id: uuid.UUID | None,
        user: User,
        new_workspace_name: str | None = None,
    ) -> PartnershipAcceptResponse:
        if user.user_type == UserType.PLATFORM_ADMIN.value:
            raise self._error(
                "PARTNERSHIP_FORBIDDEN",
                "Platform yöneticisi davet kabul edemez",
                403,
            )
        invitation = await self.get_by_token(token, lock=True)
        if not invitation.is_pending:
            raise self._error(
                "PARTNERSHIP_INVITATION_NOT_PENDING",
                "Davet tamamlanmış, iptal edilmiş veya süresi dolmuş",
                410,
            )
        if invitation.email.lower() != user.email.lower():
            raise self._error(
                "PARTNERSHIP_EMAIL_MISMATCH",
                "Bu davet farklı bir e-posta adresine gönderildi",
                403,
            )

        if target_workspace_id is None:
            assert new_workspace_name is not None
            target_workspace_id = await self._create_target_workspace(
                invitation,
                user,
                new_workspace_name,
            )

        if invitation.direction == AGENCY_INVITES_BRAND:
            assert invitation.agency_id is not None
            agency_id = invitation.agency_id
            brand_id = target_workspace_id
            await self._require_brand_owner(brand_id, user.id)
        else:
            assert invitation.brand_id is not None
            agency_id = target_workspace_id
            brand_id = invitation.brand_id
            await self._require_agency_owner(agency_id, user.id)

        agency = await self.db.scalar(
            select(Agency)
            .where(
                Agency.id == agency_id,
                Agency.status == "active",
                Agency.is_demo.is_(False),
                Agency.deleted_at.is_(None),
            )
            .with_for_update()
        )
        brand = await self.db.scalar(
            select(Brand)
            .where(
                Brand.id == brand_id,
                Brand.status == "active",
                Brand.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if agency is None or brand is None:
            raise self._error("PARTNERSHIP_TARGET_MISSING", "Hedef çalışma alanı bulunamadı", 404)
        if brand.agency_id is not None and brand.agency_id != agency.id:
            raise self._error("BRAND_ALREADY_CONNECTED", "Bu marka başka bir ajansla bağlantılı")

        accepted_at = datetime.now(UTC)
        brand.agency_id = agency.id
        invitation.accepted_at = accepted_at
        self.db.add_all(
            [
                brand,
                invitation,
                ActivityLog(
                    agency_id=agency.id,
                    brand_id=brand.id,
                    actor_user_id=user.id,
                    action="partnership.accepted",
                    entity_type="partnership_invitation",
                    entity_id=invitation.id,
                    meta={"direction": invitation.direction, "email": invitation.email},
                ),
            ]
        )
        await self.db.commit()
        return PartnershipAcceptResponse(
            agency_id=agency.id,
            brand_id=brand.id,
            redirect_to=(
                "/brand/dashboard" if invitation.direction == AGENCY_INVITES_BRAND else "/dashboard"
            ),
        )

    async def _create_target_workspace(
        self,
        invitation: PartnershipInvitation,
        user: User,
        workspace_name: str,
    ) -> uuid.UUID:
        joined_at = datetime.now(UTC)
        if invitation.direction == AGENCY_INVITES_BRAND:
            brand = Brand(
                agency_id=None,
                name=workspace_name,
                slug=await BrandRepository(self.db).generate_unique_slug(workspace_name, None),
                status=BrandStatus.ACTIVE.value,
                contact_email=user.email,
                default_language=user.locale or "tr",
            )
            self.db.add(brand)
            await self.db.flush()
            self.db.add(
                BrandMember(
                    brand_id=brand.id,
                    user_id=user.id,
                    role=BrandMemberRole.BRAND_OWNER.value,
                    status=BrandMemberStatus.ACTIVE.value,
                    joined_at=joined_at,
                )
            )
            await self.db.flush()
            return brand.id

        agency = Agency(
            name=workspace_name,
            slug=await AgencyRepository(self.db).generate_unique_slug(workspace_name),
            status=AgencyStatus.ACTIVE.value,
            owner_user_id=user.id,
        )
        self.db.add(agency)
        await self.db.flush()
        self.db.add(
            AgencyMember(
                agency_id=agency.id,
                user_id=user.id,
                role=AgencyMemberRole.OWNER.value,
                status=AgencyMemberStatus.ACTIVE.value,
                joined_at=joined_at,
            )
        )
        await self.db.flush()
        return agency.id

    async def _require_brand_owner(self, brand_id: uuid.UUID, user_id: uuid.UUID) -> None:
        member = await self.db.scalar(
            select(BrandMember).where(
                BrandMember.brand_id == brand_id,
                BrandMember.user_id == user_id,
                BrandMember.role == BrandMemberRole.BRAND_OWNER.value,
                BrandMember.status == BrandMemberStatus.ACTIVE.value,
                BrandMember.deleted_at.is_(None),
            )
        )
        if member is None:
            raise self._error(
                "PARTNERSHIP_OWNER_REQUIRED",
                "Yalnızca marka sahibi bu marka adına daveti kabul edebilir",
                403,
            )

    async def _require_agency_owner(self, agency_id: uuid.UUID, user_id: uuid.UUID) -> None:
        member = await self.db.scalar(
            select(AgencyMember).where(
                AgencyMember.agency_id == agency_id,
                AgencyMember.user_id == user_id,
                AgencyMember.role == AgencyMemberRole.OWNER.value,
                AgencyMember.status == AgencyMemberStatus.ACTIVE.value,
                AgencyMember.deleted_at.is_(None),
            )
        )
        if member is None:
            raise self._error(
                "PARTNERSHIP_OWNER_REQUIRED",
                "Yalnızca ajans sahibi bu ajans adına daveti kabul edebilir",
                403,
            )

    async def list_for_agency(self, agency_id: uuid.UUID) -> list[PartnershipInvitation]:
        return list(
            await self.db.scalars(
                select(PartnershipInvitation)
                .where(
                    PartnershipInvitation.agency_id == agency_id,
                    PartnershipInvitation.deleted_at.is_(None),
                )
                .order_by(PartnershipInvitation.created_at.desc())
            )
        )

    async def list_for_brand(self, brand_id: uuid.UUID) -> list[PartnershipInvitation]:
        return list(
            await self.db.scalars(
                select(PartnershipInvitation)
                .where(
                    PartnershipInvitation.brand_id == brand_id,
                    PartnershipInvitation.deleted_at.is_(None),
                )
                .order_by(PartnershipInvitation.created_at.desc())
            )
        )

    async def list_incoming(self, user: User) -> list[PartnershipInvitation]:
        return list(
            await self.db.scalars(
                select(PartnershipInvitation)
                .where(
                    PartnershipInvitation.email == user.email.lower(),
                    PartnershipInvitation.accepted_at.is_(None),
                    PartnershipInvitation.revoked_at.is_(None),
                    PartnershipInvitation.expires_at > datetime.now(UTC),
                    PartnershipInvitation.deleted_at.is_(None),
                )
                .order_by(PartnershipInvitation.created_at.desc())
            )
        )

    async def revoke(self, invitation_id: uuid.UUID, actor: User) -> None:
        invitation = await self.db.scalar(
            select(PartnershipInvitation)
            .where(
                PartnershipInvitation.id == invitation_id,
                PartnershipInvitation.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if invitation is None:
            raise self._error("PARTNERSHIP_INVITATION_NOT_FOUND", "Davet bulunamadı", 404)
        await self._require_source_manager(invitation, actor)
        if not invitation.is_pending:
            raise self._error(
                "PARTNERSHIP_INVITATION_NOT_PENDING",
                "Yalnızca bekleyen davet iptal edilebilir",
            )
        invitation.revoked_at = datetime.now(UTC)
        self.db.add(invitation)
        await self.db.commit()

    async def _require_source_manager(self, invitation: PartnershipInvitation, actor: User) -> None:
        if invitation.agency_id is not None:
            member = await self.db.scalar(
                select(AgencyMember).where(
                    AgencyMember.agency_id == invitation.agency_id,
                    AgencyMember.user_id == actor.id,
                    AgencyMember.role.in_(
                        [AgencyMemberRole.OWNER.value, AgencyMemberRole.ADMIN.value]
                    ),
                    AgencyMember.status == AgencyMemberStatus.ACTIVE.value,
                    AgencyMember.deleted_at.is_(None),
                )
            )
        else:
            member = await self.db.scalar(
                select(BrandMember).where(
                    BrandMember.brand_id == invitation.brand_id,
                    BrandMember.user_id == actor.id,
                    BrandMember.role == BrandMemberRole.BRAND_OWNER.value,
                    BrandMember.status == BrandMemberStatus.ACTIVE.value,
                    BrandMember.deleted_at.is_(None),
                )
            )
        if member is None:
            raise self._error("PARTNERSHIP_FORBIDDEN", "Bu daveti yönetme yetkiniz yok", 403)

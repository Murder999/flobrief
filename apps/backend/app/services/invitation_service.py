from __future__ import annotations

import contextlib
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invitation import Invitation
from app.models.user import User
from app.repositories.agency import AgencyRepository
from app.repositories.agency_member import AgencyMemberRepository
from app.repositories.brand import BrandRepository
from app.repositories.brand_member import BrandMemberRepository
from app.repositories.invitation import InvitationRepository
from app.repositories.user import UserRepository
from app.schemas.invitation import AgencyInviteRequest, BrandInviteRequest
from app.services import email_service
from app.services.entitlement_service import EntitlementService
from app.services.resend_email_provider import EmailProviderFactory
from app.services.token_service import generate_token, hash_token
from app.services.url_builder import url_builder

_403 = status.HTTP_403_FORBIDDEN
_404 = status.HTTP_404_NOT_FOUND
_409 = status.HTTP_409_CONFLICT
_410 = status.HTTP_410_GONE

_INVITATION_EXPIRE_DAYS = 7


class InvitationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.invite_repo = InvitationRepository(db)
        self.agency_repo = AgencyRepository(db)
        self.agency_member_repo = AgencyMemberRepository(db)
        self.brand_repo = BrandRepository(db)
        self.brand_member_repo = BrandMemberRepository(db)
        self.user_repo = UserRepository(db)

    async def create_agency_invite(
        self,
        agency_id: uuid.UUID,
        data: AgencyInviteRequest,
        inviter: User,
    ) -> tuple[Invitation, str]:
        """Returns (invitation, plaintext_token)."""
        from app.models.enums import AgencyMemberRole

        agency = await self.agency_repo.get_by_id(agency_id)
        if agency is None:
            raise HTTPException(_404, "Agency bulunamadı")

        inviter_member = await self.agency_member_repo.get_membership(agency_id, inviter.id)
        if inviter_member is None:
            raise HTTPException(_403, "Bu agency'ye erişim yetkiniz yok")

        can_invite = {AgencyMemberRole.OWNER.value, AgencyMemberRole.ADMIN.value}
        if inviter_member.role not in can_invite:
            raise HTTPException(_403, "Üye davet etme yetkiniz yok")

        # Block platform_admin creation via invite (belt-and-suspenders, schema also blocks)
        if data.role == "platform_admin":
            raise HTTPException(_403, "platform_admin daveti yasaktır")

        entitlements = EntitlementService(self.db)
        await entitlements.check_user_limit(agency_id, lock=True)
        await entitlements.check_pending_invite_limit(agency_id, lock=True)

        # Check if already a member
        existing_user = await self.user_repo.get_by_email(data.email)
        if existing_user:
            existing_member = await self.agency_member_repo.get_membership(
                agency_id, existing_user.id
            )
            if existing_member is not None:
                raise HTTPException(_409, "Bu kullanıcı zaten bu agency'ye üye")

        # Check if there's already a pending invite
        existing_invite = await self.invite_repo.get_pending_for_email_and_agency(
            data.email, agency_id, "agency"
        )
        if existing_invite:
            raise HTTPException(_409, "Bu e-posta için bekleyen bir davet zaten var")

        plaintext = generate_token(48)
        token_hash = hash_token(plaintext)
        expires_at = datetime.now(UTC) + timedelta(days=_INVITATION_EXPIRE_DAYS)

        invitation = await self.invite_repo.create(
            agency_id=agency_id,
            brand_id=None,
            invitation_type="agency",
            email=data.email.lower(),
            role=data.role,
            token_hash=token_hash,
            invited_by=inviter.id,
            expires_at=expires_at,
        )
        await self.db.flush()

        from app.repositories.activity import ActivityLogRepository

        await ActivityLogRepository(self.db).create(
            action="user.invited",
            entity_type="invitation",
            entity_id=invitation.id,
            agency_id=agency_id,
            actor_user_id=inviter.id,
            meta={"email": data.email, "role": data.role, "invitation_type": "agency"},
        )

        await self.db.commit()
        await self.db.refresh(invitation)

        await self._send_agency_invite_email(
            to_email=data.email,
            agency_name=agency.name,
            inviter_name=inviter.full_name,
            role=data.role,
            token=plaintext,
            message=data.message,
        )

        return invitation, plaintext

    async def create_brand_invite(
        self,
        brand_id: uuid.UUID,
        agency_id: uuid.UUID,
        data: BrandInviteRequest,
        inviter: User,
    ) -> tuple[Invitation, str]:
        brand = await self.brand_repo.get_by_id_and_agency(brand_id, agency_id)
        if brand is None:
            raise HTTPException(_404, "Marka bulunamadı")

        from app.models.enums import AgencyMemberRole, BrandMemberRole

        # Either an agency owner/admin, or the brand's own owner/manager, may invite.
        agency_member = await self.agency_member_repo.get_membership(agency_id, inviter.id)
        agency_can_invite = agency_member is not None and agency_member.role in {
            AgencyMemberRole.OWNER.value,
            AgencyMemberRole.ADMIN.value,
        }
        brand_member = await self.brand_member_repo.get_membership(brand_id, inviter.id)
        brand_can_invite = brand_member is not None and brand_member.role in {
            BrandMemberRole.BRAND_OWNER.value,
            BrandMemberRole.BRAND_MANAGER.value,
        }
        if not agency_can_invite and not brand_can_invite:
            raise HTTPException(_403, "Marka üyesi davet etme yetkiniz yok")

        if data.role == "platform_admin":
            raise HTTPException(_403, "platform_admin daveti yasaktır")

        entitlements = EntitlementService(self.db)
        await entitlements.check_brand_user_limit(agency_id, brand_id, lock=True)
        await entitlements.check_pending_invite_limit(agency_id, brand_id, lock=True)

        existing_user = await self.user_repo.get_by_email(data.email)
        if existing_user:
            existing_member = await self.brand_member_repo.get_membership(
                brand_id, existing_user.id
            )
            if existing_member is not None:
                raise HTTPException(_409, "Bu kullanıcı zaten bu markaya üye")

        existing_invite = await self.invite_repo.get_pending_for_email_and_agency(
            data.email, agency_id, "brand"
        )
        if existing_invite and existing_invite.brand_id == brand_id:
            raise HTTPException(_409, "Bu e-posta için bekleyen bir davet zaten var")

        plaintext = generate_token(48)
        token_hash = hash_token(plaintext)
        expires_at = datetime.now(UTC) + timedelta(days=_INVITATION_EXPIRE_DAYS)

        invitation = await self.invite_repo.create(
            agency_id=agency_id,
            brand_id=brand_id,
            invitation_type="brand",
            email=data.email.lower(),
            role=data.role,
            token_hash=token_hash,
            invited_by=inviter.id,
            expires_at=expires_at,
        )
        await self.db.flush()

        from app.repositories.activity import ActivityLogRepository

        await ActivityLogRepository(self.db).create(
            action="user.invited",
            entity_type="invitation",
            entity_id=invitation.id,
            agency_id=agency_id,
            actor_user_id=inviter.id,
            meta={
                "email": data.email,
                "role": data.role,
                "invitation_type": "brand",
                "brand_id": str(brand_id),
            },
        )

        await self.db.commit()
        await self.db.refresh(invitation)

        agency = await self.agency_repo.get_by_id(agency_id)
        agency_name = agency.name if agency else ""

        await self._send_brand_invite_email(
            to_email=data.email,
            agency_name=agency_name,
            brand_name=brand.name,
            inviter_name=inviter.full_name,
            role=data.role,
            token=plaintext,
            message=data.message,
        )

        return invitation, plaintext

    async def get_by_token(self, token: str) -> Invitation:
        token_hash = hash_token(token)
        invitation = await self.invite_repo.get_by_token_hash(token_hash)
        if invitation is None:
            raise HTTPException(_404, "Davet bulunamadı")
        return invitation

    async def accept_invitation(self, token: str, user: User) -> None:
        from datetime import UTC, datetime

        from app.models.enums import AgencyMemberStatus, BrandMemberStatus

        invitation = await self.get_by_token(token)

        if not invitation.is_pending:
            if invitation.is_accepted:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bu davet zaten kabul edildi")
            if invitation.is_revoked:
                raise HTTPException(_410, "Bu davet iptal edildi")
            raise HTTPException(_410, "Bu davet süresi dolmuş")

        if user.email.lower() != invitation.email.lower():
            raise HTTPException(_403, "Bu davet farklı bir e-posta adresine gönderildi")

        if invitation.invitation_type == "agency":
            existing = await self.agency_member_repo.get_membership(invitation.agency_id, user.id)
            if existing is None:
                await self.agency_member_repo.create(
                    agency_id=invitation.agency_id,
                    user_id=user.id,
                    role=invitation.role,
                    status=AgencyMemberStatus.ACTIVE.value,
                    joined_at=datetime.now(UTC),
                )
        else:
            if invitation.brand_id is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Geçersiz davet")
            existing = await self.brand_member_repo.get_membership(invitation.brand_id, user.id)
            if existing is None:
                await self.brand_member_repo.create(
                    brand_id=invitation.brand_id,
                    user_id=user.id,
                    role=invitation.role,
                    status=BrandMemberStatus.ACTIVE.value,
                    joined_at=datetime.now(UTC),
                )

        now = datetime.now(UTC)
        await self.invite_repo.update(invitation, accepted_at=now)

        from app.repositories.activity import ActivityLogRepository

        await ActivityLogRepository(self.db).create(
            action="invitation.accepted",
            entity_type="invitation",
            entity_id=invitation.id,
            agency_id=invitation.agency_id,
            actor_user_id=user.id,
            meta={"email": invitation.email, "role": invitation.role},
        )

        await self.db.commit()

    async def revoke_invitation(self, token: str, actor: User) -> None:
        from datetime import UTC, datetime

        invitation = await self.get_by_token(token)

        inviter_member = await self.agency_member_repo.get_membership(
            invitation.agency_id, actor.id
        )
        from app.models.enums import AgencyMemberRole

        allowed = {AgencyMemberRole.OWNER.value, AgencyMemberRole.ADMIN.value}
        if inviter_member is None or inviter_member.role not in allowed:
            raise HTTPException(_403, "Davet iptal etme yetkiniz yok")

        if not invitation.is_pending:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Bu davet zaten tamamlandı veya iptal edildi"
            )

        now = datetime.now(UTC)
        await self.invite_repo.update(invitation, revoked_at=now)

        from app.repositories.activity import ActivityLogRepository

        await ActivityLogRepository(self.db).create(
            action="invitation.revoked",
            entity_type="invitation",
            entity_id=invitation.id,
            agency_id=invitation.agency_id,
            actor_user_id=actor.id,
            meta={"email": invitation.email, "role": invitation.role},
        )

        await self.db.commit()

    async def revoke_by_id(self, invitation_id: uuid.UUID, actor: User) -> None:
        from datetime import UTC, datetime

        invitation = await self.invite_repo.get_by_id(invitation_id)
        if invitation is None:
            raise HTTPException(_404, "Davet bulunamadı")

        if not await self._can_manage_invitation(invitation, actor):
            raise HTTPException(_403, "Davet iptal etme yetkiniz yok")

        if not invitation.is_pending:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Bu davet zaten tamamlandı veya iptal edildi"
            )

        now = datetime.now(UTC)
        await self.invite_repo.update(invitation, revoked_at=now)

        from app.repositories.activity import ActivityLogRepository

        await ActivityLogRepository(self.db).create(
            action="invitation.revoked",
            entity_type="invitation",
            entity_id=invitation.id,
            agency_id=invitation.agency_id,
            actor_user_id=actor.id,
            meta={"email": invitation.email, "role": invitation.role},
        )

        await self.db.commit()

    async def resend_by_id(self, invitation_id: uuid.UUID, actor: User) -> tuple[Invitation, str]:
        from datetime import UTC, datetime, timedelta

        invitation = await self.invite_repo.get_by_id(invitation_id)
        if invitation is None:
            raise HTTPException(_404, "Davet bulunamadı")

        if not await self._can_manage_invitation(invitation, actor):
            raise HTTPException(_403, "Davet yeniden gönderme yetkiniz yok")

        if not invitation.is_pending:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Bekleyen olmayan davet yeniden gönderilemez"
            )

        plaintext = generate_token(48)
        new_hash = hash_token(plaintext)
        new_expires = datetime.now(UTC) + timedelta(days=_INVITATION_EXPIRE_DAYS)

        await self.invite_repo.update(
            invitation,
            token_hash=new_hash,
            expires_at=new_expires,
            resent_count=invitation.resent_count + 1,
        )

        from app.repositories.activity import ActivityLogRepository

        await ActivityLogRepository(self.db).create(
            action="invitation.resent",
            entity_type="invitation",
            entity_id=invitation.id,
            agency_id=invitation.agency_id,
            actor_user_id=actor.id,
            meta={"email": invitation.email, "role": invitation.role},
        )

        await self.db.commit()
        await self.db.refresh(invitation)

        agency = await self.agency_repo.get_by_id(invitation.agency_id)
        agency_name = agency.name if agency else ""

        if invitation.invitation_type == "agency":
            await self._send_agency_invite_email(
                to_email=invitation.email,
                agency_name=agency_name,
                inviter_name=actor.full_name,
                role=invitation.role,
                token=plaintext,
                message=None,
            )
        else:
            brand = await self.brand_repo.get_by_id(invitation.brand_id)  # type: ignore[arg-type]
            brand_name = brand.name if brand else ""
            await self._send_brand_invite_email(
                to_email=invitation.email,
                agency_name=agency_name,
                brand_name=brand_name,
                inviter_name=actor.full_name,
                role=invitation.role,
                token=plaintext,
                message=None,
            )

        return invitation, plaintext

    async def _can_manage_invitation(self, invitation: Invitation, actor: User) -> bool:
        """Agency owner/admin can manage any invite; a brand's own owner/manager
        can manage that brand's invites."""
        from app.models.enums import AgencyMemberRole, BrandMemberRole

        agency_member = await self.agency_member_repo.get_membership(invitation.agency_id, actor.id)
        if agency_member is not None and agency_member.role in {
            AgencyMemberRole.OWNER.value,
            AgencyMemberRole.ADMIN.value,
        }:
            return True
        if invitation.invitation_type == "brand" and invitation.brand_id is not None:
            brand_member = await self.brand_member_repo.get_membership(
                invitation.brand_id, actor.id
            )
            if brand_member is not None and brand_member.role in {
                BrandMemberRole.BRAND_OWNER.value,
                BrandMemberRole.BRAND_MANAGER.value,
            }:
                return True
        return False

    async def reject_invitation(self, invitation_id: uuid.UUID, user: User) -> None:
        """User rejects their own invitation."""
        from datetime import UTC, datetime

        invitation = await self.invite_repo.get_by_id(invitation_id)
        if invitation is None:
            raise HTTPException(_404, "Davet bulunamadı")

        if user.email.lower() != invitation.email.lower():
            raise HTTPException(_403, "Bu davet farklı bir e-posta adresine gönderildi")

        if not invitation.is_pending:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Bu davet zaten tamamlandı, iptal edildi veya reddedildi",
            )

        now = datetime.now(UTC)
        await self.invite_repo.update(invitation, rejected_at=now)

        from app.repositories.activity import ActivityLogRepository

        await ActivityLogRepository(self.db).create(
            action="invitation.rejected",
            entity_type="invitation",
            entity_id=invitation.id,
            agency_id=invitation.agency_id,
            actor_user_id=user.id,
            meta={"email": invitation.email, "role": invitation.role},
        )

        await self.db.commit()

    async def accept_by_id(self, invitation_id: uuid.UUID, user: User) -> None:
        """Accept an invitation by ID (for logged-in users viewing their pending invitations)."""
        from datetime import UTC, datetime

        from app.models.enums import AgencyMemberStatus, BrandMemberStatus

        invitation = await self.invite_repo.get_by_id(invitation_id)
        if invitation is None:
            raise HTTPException(_404, "Davet bulunamadı")

        if not invitation.is_pending:
            if invitation.is_accepted:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bu davet zaten kabul edildi")
            if invitation.is_revoked:
                raise HTTPException(_410, "Bu davet iptal edildi")
            if invitation.is_rejected:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bu davet reddedildi")
            raise HTTPException(_410, "Bu davet süresi dolmuş")

        if user.email.lower() != invitation.email.lower():
            raise HTTPException(_403, "Bu davet farklı bir e-posta adresine gönderildi")

        if invitation.invitation_type == "agency":
            existing = await self.agency_member_repo.get_membership(invitation.agency_id, user.id)
            if existing is None:
                await self.agency_member_repo.create(
                    agency_id=invitation.agency_id,
                    user_id=user.id,
                    role=invitation.role,
                    status=AgencyMemberStatus.ACTIVE.value,
                    joined_at=datetime.now(UTC),
                )
        else:
            if invitation.brand_id is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Geçersiz davet")
            existing = await self.brand_member_repo.get_membership(invitation.brand_id, user.id)
            if existing is None:
                await self.brand_member_repo.create(
                    brand_id=invitation.brand_id,
                    user_id=user.id,
                    role=invitation.role,
                    status=BrandMemberStatus.ACTIVE.value,
                    joined_at=datetime.now(UTC),
                )

        now = datetime.now(UTC)
        await self.invite_repo.update(invitation, accepted_at=now)

        from app.repositories.activity import ActivityLogRepository

        await ActivityLogRepository(self.db).create(
            action="invitation.accepted",
            entity_type="invitation",
            entity_id=invitation.id,
            agency_id=invitation.agency_id,
            actor_user_id=user.id,
            meta={"email": invitation.email, "role": invitation.role},
        )

        await self.db.commit()

    # ── Email helpers ─────────────────────────────────────────────────────────

    async def _send_agency_invite_email(
        self,
        to_email: str,
        agency_name: str,
        inviter_name: str,
        role: str,
        token: str,
        message: str | None,
    ) -> None:
        """Send through Resend when configured; skip safely when disabled."""
        accept_url = url_builder.invite_link(token)
        subject = f"Flobrief — {agency_name} Daveti"
        html = email_service.build_agency_invite_html(
            inviter_name=inviter_name,
            agency_name=agency_name,
            role=role,
            accept_url=accept_url,
            message=message,
        )
        with contextlib.suppress(Exception):
            provider = await EmailProviderFactory.get_provider(self.db)
            if provider.is_active():
                await provider.send(to_email=to_email, subject=subject, html=html)

    async def _send_brand_invite_email(
        self,
        to_email: str,
        agency_name: str,
        brand_name: str,
        inviter_name: str,
        role: str,
        token: str,
        message: str | None,
    ) -> None:
        """Send through Resend when configured; skip safely when disabled."""
        accept_url = url_builder.invite_link(token)
        subject = f"Flobrief — {brand_name} Marka Daveti"
        html = email_service.build_brand_invite_html(
            inviter_name=inviter_name,
            agency_name=agency_name,
            brand_name=brand_name,
            role=role,
            accept_url=accept_url,
            message=message,
        )
        with contextlib.suppress(Exception):
            provider = await EmailProviderFactory.get_provider(self.db)
            if provider.is_active():
                await provider.send(to_email=to_email, subject=subject, html=html)

    async def resend_invitation(self, token: str, actor: User) -> tuple[Invitation, str]:
        from datetime import UTC, datetime, timedelta

        invitation = await self.get_by_token(token)

        inviter_member = await self.agency_member_repo.get_membership(
            invitation.agency_id, actor.id
        )
        from app.models.enums import AgencyMemberRole

        allowed = {AgencyMemberRole.OWNER.value, AgencyMemberRole.ADMIN.value}
        if inviter_member is None or inviter_member.role not in allowed:
            raise HTTPException(_403, "Davet yeniden gönderme yetkiniz yok")

        if not invitation.is_pending:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Bekleyen olmayan davet yeniden gönderilemez"
            )

        plaintext = generate_token(48)
        new_hash = hash_token(plaintext)
        new_expires = datetime.now(UTC) + timedelta(days=_INVITATION_EXPIRE_DAYS)

        await self.invite_repo.update(
            invitation,
            token_hash=new_hash,
            expires_at=new_expires,
            resent_count=invitation.resent_count + 1,
        )
        await self.db.commit()
        await self.db.refresh(invitation)

        agency = await self.agency_repo.get_by_id(invitation.agency_id)
        agency_name = agency.name if agency else ""

        if invitation.invitation_type == "agency":
            await self._send_agency_invite_email(
                to_email=invitation.email,
                agency_name=agency_name,
                inviter_name=actor.full_name,
                role=invitation.role,
                token=plaintext,
                message=None,
            )
        else:
            brand = await self.brand_repo.get_by_id(invitation.brand_id)  # type: ignore[arg-type]
            brand_name = brand.name if brand else ""
            await self._send_brand_invite_email(
                to_email=invitation.email,
                agency_name=agency_name,
                brand_name=brand_name,
                inviter_name=actor.full_name,
                role=invitation.role,
                token=plaintext,
                message=None,
            )

        return invitation, plaintext

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.models.agency import Agency
from app.models.demo_sandbox import DemoSandbox
from app.models.enums import (
    AgencyMemberRole,
    AgencyMemberStatus,
    BrandMemberStatus,
    UserType,
)
from app.models.invitation import Invitation
from app.models.user import User
from app.repositories.agency import AgencyRepository
from app.repositories.agency_member import AgencyMemberRepository
from app.repositories.brand import BrandRepository
from app.repositories.brand_member import BrandMemberRepository
from app.repositories.invitation import InvitationRepository
from app.repositories.user import UserRepository
from app.schemas.invitation import (
    AgencyInviteRequest,
    BrandInviteRequest,
    InvitationSignupRequest,
)
from app.services import email_service
from app.services.auth_service import AuthService
from app.services.email_i18n import email_text, normalize_email_locale
from app.services.entitlement_service import EntitlementService
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

    @staticmethod
    def invitation_state(invitation: Invitation) -> str:
        if invitation.is_accepted:
            return "accepted"
        if invitation.is_revoked:
            return "revoked"
        if invitation.is_rejected:
            return "declined"
        if invitation.is_pending:
            return "pending"
        return "expired"

    @staticmethod
    def expected_user_type(invitation: Invitation) -> str:
        return (
            UserType.BRAND_USER.value
            if invitation.invitation_type == "brand"
            else UserType.AGENCY_USER.value
        )

    @staticmethod
    def _domain_error(status_code: int, code: str, message: str) -> HTTPException:
        return HTTPException(status_code=status_code, detail={"code": code, "message": message})

    async def _validate_target(self, invitation: Invitation) -> None:
        if invitation.invitation_type not in {"agency", "brand"}:
            raise self._domain_error(
                _410,
                "INVITATION_TARGET_MISSING",
                "Davet hedefi geçersiz",
            )
        agency = await self.agency_repo.get_by_id(invitation.agency_id)
        if agency is None:
            raise self._domain_error(
                _410,
                "INVITATION_TARGET_MISSING",
                "Davet hedefi artık mevcut değil",
            )
        if invitation.invitation_type == "brand":
            if invitation.brand_id is None:
                raise self._domain_error(_410, "INVITATION_TARGET_MISSING", "Davet hedefi geçersiz")
            brand = await self.brand_repo.get_by_id_and_agency(
                invitation.brand_id, invitation.agency_id
            )
            if brand is None:
                raise self._domain_error(
                    _410, "INVITATION_TARGET_MISSING", "Davet edilen marka artık mevcut değil"
                )

    def _require_pending(self, invitation: Invitation) -> None:
        state = self.invitation_state(invitation)
        if state == "pending":
            return
        status_code = status.HTTP_409_CONFLICT if state == "accepted" else _410
        messages = {
            "accepted": "Bu davet zaten kabul edildi",
            "revoked": "Bu davet iptal edildi",
            "declined": "Bu davet reddedildi",
            "expired": "Bu davetin süresi doldu",
        }
        raise self._domain_error(
            status_code,
            f"INVITATION_{state.upper()}",
            messages[state],
        )

    def _require_compatible_user(self, invitation: Invitation, user: User) -> None:
        expected = self.expected_user_type(invitation)
        if user.user_type != expected:
            raise self._domain_error(
                _409,
                "INVITATION_ACCOUNT_TYPE_CONFLICT",
                "Bu hesap türü davet edilen portal ile uyumlu değil. "
                "Destek ekibiyle iletişime geçin.",
            )

    async def _ensure_external_invitation_allowed(
        self,
        agency_id: uuid.UUID,
        actor: User,
    ) -> None:
        demo_agency = await self.db.scalar(
            select(Agency.id).where(
                Agency.id == agency_id,
                Agency.is_demo.is_(True),
                Agency.deleted_at.is_(None),
            )
        )
        demo_actor = await self.db.scalar(
            select(DemoSandbox.id).where(
                or_(
                    DemoSandbox.owner_user_id == actor.id,
                    DemoSandbox.brand_user_id == actor.id,
                ),
                DemoSandbox.deleted_at.is_(None),
            )
        )
        if demo_agency is not None or demo_actor is not None:
            raise HTTPException(
                _403,
                "Demo ortamında davet işlemleri kullanılamaz",
            )

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
        await self._ensure_external_invitation_allowed(agency_id, inviter)

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
            locale=existing_user.locale if existing_user else None,
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
        await self._ensure_external_invitation_allowed(agency_id, inviter)

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
            locale=existing_user.locale if existing_user else brand.default_language,
        )

        return invitation, plaintext

    async def get_by_token(self, token: str, *, lock: bool = False) -> Invitation:
        token_hash = hash_token(token)
        invitation = await self.invite_repo.get_by_token_hash(token_hash, lock=lock)
        if invitation is None:
            raise HTTPException(_404, "Davet bulunamadı")
        return invitation

    async def accept_invitation(self, token: str, user: User) -> None:
        invitation = await self.get_by_token(token, lock=True)
        await self._ensure_external_invitation_allowed(invitation.agency_id, user)
        await self._accept_pending_invitation(invitation, user)
        await self.db.commit()

    async def signup_and_accept(
        self,
        token: str,
        data: InvitationSignupRequest,
        *,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, str, str, str]:
        """Atomically create the invitation-derived user, membership, and session."""
        invitation = await self.get_by_token(token, lock=True)
        self._require_pending(invitation)
        await self._validate_target(invitation)

        existing_user = await self.db.scalar(
            select(User)
            .where(User.email == invitation.email.lower(), User.deleted_at.is_(None))
            .with_for_update()
        )
        if existing_user is not None:
            raise self._domain_error(
                _409,
                "INVITATION_ACCOUNT_EXISTS",
                "Bu e-posta ile bir PostPiloter hesabı zaten mevcut. Giriş yaparak devam edin.",
            )

        user = User(
            email=invitation.email.lower(),
            password_hash=hash_password(data.password),
            full_name=data.full_name,
            user_type=self.expected_user_type(invitation),
            is_active=True,
            is_verified=True,
            phone_number=data.phone_number,
            whatsapp_opt_in=data.whatsapp_opt_in,
            locale=data.locale,
        )
        if data.whatsapp_opt_in:
            user.whatsapp_opt_in_at = datetime.now(UTC)
        self.db.add(user)

        try:
            await self.db.flush()
            await self._accept_pending_invitation(invitation, user)
            access_token, refresh_token = await AuthService(self.db).create_session(
                user,
                ip=ip,
                user_agent=user_agent,
            )
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise self._domain_error(
                _409,
                "INVITATION_SIGNUP_CONFLICT",
                "Hesap veya üyelik eş zamanlı olarak oluşturuldu. Davet sayfasını yenileyin.",
            ) from exc

        redirect_to = "/brand/dashboard" if invitation.invitation_type == "brand" else "/dashboard"
        return user, access_token, refresh_token, redirect_to

    async def _accept_pending_invitation(self, invitation: Invitation, user: User) -> None:
        self._require_pending(invitation)
        await self._validate_target(invitation)

        if user.email.lower() != invitation.email.lower():
            raise self._domain_error(
                _403,
                "INVITATION_EMAIL_MISMATCH",
                "Bu davet farklı bir e-posta adresine gönderildi",
            )
        self._require_compatible_user(invitation, user)

        entitlements = EntitlementService(self.db)
        joined_at = datetime.now(UTC)
        if invitation.invitation_type == "agency":
            existing = await self.agency_member_repo.get_membership(invitation.agency_id, user.id)
            if existing is not None:
                raise self._domain_error(
                    _409,
                    "INVITATION_MEMBERSHIP_EXISTS",
                    "Bu hesap zaten ajans üyesi. Destek ekibiyle iletişime geçin.",
                )
            await entitlements.check_user_limit(
                invitation.agency_id,
                lock=True,
                exclude_invitation_id=invitation.id,
            )
            await self.agency_member_repo.create(
                agency_id=invitation.agency_id,
                user_id=user.id,
                role=invitation.role,
                status=AgencyMemberStatus.ACTIVE.value,
                joined_at=joined_at,
            )
            if invitation.role == AgencyMemberRole.OWNER.value:
                agency = await self.agency_repo.get_by_id(invitation.agency_id)
                if agency is not None and agency.owner_user_id is None:
                    agency.owner_user_id = user.id
                    self.db.add(agency)
        else:
            assert invitation.brand_id is not None
            existing = await self.brand_member_repo.get_membership(invitation.brand_id, user.id)
            if existing is not None:
                raise self._domain_error(
                    _409,
                    "INVITATION_MEMBERSHIP_EXISTS",
                    "Bu hesap zaten marka üyesi. Destek ekibiyle iletişime geçin.",
                )
            await entitlements.check_brand_user_limit(
                invitation.agency_id,
                invitation.brand_id,
                lock=True,
                exclude_invitation_id=invitation.id,
            )
            await self.brand_member_repo.create(
                brand_id=invitation.brand_id,
                user_id=user.id,
                role=invitation.role,
                status=BrandMemberStatus.ACTIVE.value,
                joined_at=joined_at,
            )

        await self.invite_repo.update(invitation, accepted_at=joined_at)

        from app.repositories.activity import ActivityLogRepository

        await ActivityLogRepository(self.db).create(
            action="invitation.accepted",
            entity_type="invitation",
            entity_id=invitation.id,
            agency_id=invitation.agency_id,
            brand_id=invitation.brand_id,
            actor_user_id=user.id,
            meta={
                "email": invitation.email,
                "role": invitation.role,
                "invitation_type": invitation.invitation_type,
            },
        )

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
        await self._ensure_external_invitation_allowed(invitation.agency_id, actor)

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
        invitation = await self.db.scalar(
            select(Invitation)
            .where(
                Invitation.id == invitation_id,
                Invitation.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if invitation is None:
            raise HTTPException(_404, "Davet bulunamadı")
        await self._ensure_external_invitation_allowed(invitation.agency_id, user)
        await self._accept_pending_invitation(invitation, user)
        await self.db.commit()

    # ── Email helpers ─────────────────────────────────────────────────────────

    async def send_invitation_email(
        self,
        invitation: Invitation,
        token: str,
        *,
        inviter_name: str,
        locale: str | None = None,
    ) -> None:
        agency = await self.agency_repo.get_by_id(invitation.agency_id)
        agency_name = agency.name if agency else ""
        if invitation.invitation_type == "agency":
            await self._send_agency_invite_email(
                to_email=invitation.email,
                agency_name=agency_name,
                inviter_name=inviter_name,
                role=invitation.role,
                token=token,
                message=None,
                locale=locale,
            )
            return

        brand = (
            await self.brand_repo.get_by_id(invitation.brand_id)
            if invitation.brand_id is not None
            else None
        )
        await self._send_brand_invite_email(
            to_email=invitation.email,
            agency_name=agency_name,
            brand_name=brand.name if brand else "",
            inviter_name=inviter_name,
            role=invitation.role,
            token=token,
            message=None,
            locale=locale,
        )

    async def _send_agency_invite_email(
        self,
        to_email: str,
        agency_name: str,
        inviter_name: str,
        role: str,
        token: str,
        message: str | None,
        locale: str | None = None,
    ) -> None:
        """Send through Resend when configured; skip safely when disabled."""
        lang = normalize_email_locale(locale)
        accept_url = url_builder.invite_link(token)
        subject = f"{settings.EMAIL_FROM_NAME} — {agency_name} {email_text(lang, 'invite_title')}"
        html = email_service.build_agency_invite_html(
            inviter_name=inviter_name,
            agency_name=agency_name,
            role=role,
            accept_url=accept_url,
            message=message,
            locale=lang,
        )
        await email_service.deliver_transactional_email(
            self.db,
            to_email=to_email,
            subject=subject,
            html_body=html,
            message_type="agency_invitation",
        )

    async def _send_brand_invite_email(
        self,
        to_email: str,
        agency_name: str,
        brand_name: str,
        inviter_name: str,
        role: str,
        token: str,
        message: str | None,
        locale: str | None = None,
    ) -> None:
        """Send through Resend when configured; skip safely when disabled."""
        lang = normalize_email_locale(locale)
        accept_url = url_builder.invite_link(token)
        subject = (
            f"{settings.EMAIL_FROM_NAME} — {brand_name} "
            f"{email_text(lang, 'brand_invite_title')}"
        )
        html = email_service.build_brand_invite_html(
            inviter_name=inviter_name,
            agency_name=agency_name,
            brand_name=brand_name,
            role=role,
            accept_url=accept_url,
            message=message,
            locale=lang,
        )
        await email_service.deliver_transactional_email(
            self.db,
            to_email=to_email,
            subject=subject,
            html_body=html,
            message_type="brand_invitation",
        )

    async def resend_invitation(self, token: str, actor: User) -> tuple[Invitation, str]:
        from datetime import UTC, datetime, timedelta

        invitation = await self.get_by_token(token)
        await self._ensure_external_invitation_allowed(invitation.agency_id, actor)

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

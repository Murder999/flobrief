from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
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
from app.models.user import User
from app.repositories.agency import AgencyRepository
from app.repositories.brand import BrandRepository
from app.repositories.user import UserRepository
from app.repositories.user_token import UserTokenRepository
from app.schemas.auth import (
    ChangePasswordRequest,
    EmailVerifyRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    ResendVerificationRequest,
)
from app.services import email_service
from app.services.demo_access import ensure_demo_user_access, get_demo_sandbox_for_user
from app.services.token_service import (
    TOKEN_TYPE_EMAIL_VERIFY,
    TOKEN_TYPE_PASSWORD_RESET,
    TOKEN_TYPE_REFRESH,
    generate_token,
    get_access_token_expire_minutes,
    get_email_verify_expires,
    get_password_reset_expires,
    get_refresh_token_expires,
    hash_token,
    new_token_family,
)

_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="E-posta veya şifre hatalı",
    headers={"WWW-Authenticate": "Bearer"},
)

_ERR_400 = status.HTTP_400_BAD_REQUEST
_ERR_401 = status.HTTP_401_UNAUTHORIZED
_ERR_403 = status.HTTP_403_FORBIDDEN
_ERR_409 = status.HTTP_409_CONFLICT


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.token_repo = UserTokenRepository(db)

    async def register(
        self,
        data: RegisterRequest,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> User:
        if await self.user_repo.email_exists(data.email):
            raise HTTPException(
                status_code=_ERR_409,
                detail="Bu e-posta adresi zaten kayıtlı",
            )

        preferred_user_type = (
            UserType.BRAND_USER.value
            if data.workspace_type == "brand"
            else UserType.AGENCY_USER.value
        )
        user = await self.user_repo.create(
            email=data.email,
            password_hash=hash_password(data.password),
            full_name=data.full_name,
            user_type=preferred_user_type,
            is_active=True,
            is_verified=settings.is_development,
            phone_number=data.phone_number,
            whatsapp_opt_in=data.whatsapp_opt_in,
            locale=data.locale,
        )
        if data.whatsapp_opt_in:
            user.whatsapp_opt_in_at = datetime.now(UTC)

        workspace_name = data.workspace_name or data.full_name
        joined_at = datetime.now(UTC)
        if data.workspace_type == "brand":
            brand_repo = BrandRepository(self.db)
            brand = Brand(
                agency_id=None,
                name=workspace_name,
                slug=await brand_repo.generate_unique_slug(workspace_name, None),
                status=BrandStatus.ACTIVE.value,
                default_language=data.locale,
                contact_email=data.email,
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
        else:
            agency_repo = AgencyRepository(self.db)
            agency = Agency(
                name=workspace_name,
                slug=await agency_repo.generate_unique_slug(workspace_name),
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

        if not settings.is_development:
            token_plaintext = generate_token()
            await self.token_repo.create(
                user_id=user.id,
                token_hash=hash_token(token_plaintext),
                token_family=new_token_family(),
                token_type=TOKEN_TYPE_EMAIL_VERIFY,
                expires_at=get_email_verify_expires(),
                ip_address=ip,
                user_agent=user_agent,
            )
            await self.db.commit()

            await email_service.send_verification_email(
                self.db, user.email, user.full_name, token_plaintext, user.locale
            )
        else:
            await self.db.commit()

        return user

    async def login(
        self,
        data: LoginRequest,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, str, str]:
        user = await self.user_repo.get_by_email(data.email)
        if user is None or user.is_deleted:
            raise _INVALID_CREDENTIALS

        if not verify_password(data.password, user.password_hash):
            raise _INVALID_CREDENTIALS

        if not user.is_active:
            raise HTTPException(status_code=_ERR_403, detail="Hesap devre dışı")

        if not user.is_verified:
            raise HTTPException(
                status_code=_ERR_403,
                detail="E-posta adresinizi doğrulamanız gerekmektedir",
            )

        if user.user_type == UserType.PLATFORM_ADMIN.value:
            # Tenant login must not disclose that an account belongs to the
            # hidden platform channel or reveal that channel's route.
            raise _INVALID_CREDENTIALS

        await ensure_demo_user_access(self.db, user.id)
        access_token, refresh_plaintext = await self.create_session(
            user,
            ip=ip,
            user_agent=user_agent,
        )
        await self.db.commit()

        return user, access_token, refresh_plaintext

    async def create_session(
        self,
        user: User,
        *,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, str]:
        """Stage a tenant login session without committing the surrounding transaction."""
        expire_minutes = get_access_token_expire_minutes(user.user_type)
        access_token = create_access_token(
            subject=str(user.id),
            extra_claims={"user_type": user.user_type},
            expire_minutes=expire_minutes,
        )

        refresh_plaintext = generate_token()
        await self.token_repo.create(
            user_id=user.id,
            token_hash=hash_token(refresh_plaintext),
            token_family=new_token_family(),
            token_type=TOKEN_TYPE_REFRESH,
            expires_at=get_refresh_token_expires(user.user_type),
            ip_address=ip,
            user_agent=user_agent,
        )

        user.last_login_at = datetime.now(UTC)
        self.db.add(user)
        await self.db.flush()
        return access_token, refresh_plaintext

    async def platform_admin_login(
        self,
        data: LoginRequest,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> User:
        """Verify platform_admin credentials. Token creation is handled by the endpoint."""
        from app.repositories.platform_audit_log import PlatformAuditLogRepository

        audit_repo = PlatformAuditLogRepository(self.db)

        user = await self.user_repo.get_by_email(data.email)
        login_failed = (
            user is None
            or user.is_deleted
            or not verify_password(data.password, user.password_hash)
            or user.user_type != UserType.PLATFORM_ADMIN.value
            or not user.is_active
        )

        if login_failed:
            if user is not None and user.user_type == UserType.PLATFORM_ADMIN.value:
                await audit_repo.create(
                    admin_user_id=user.id,
                    action="platform_admin.login_failed",
                    ip_address=ip,
                    user_agent=user_agent,
                    meta={"reason": "bad_credentials"},
                )
                await self.db.commit()
            raise _INVALID_CREDENTIALS

        assert user is not None
        user.last_login_at = datetime.now(UTC)
        self.db.add(user)
        await self.db.flush()
        return user

    async def refresh_tokens(
        self,
        refresh_token_plaintext: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, str, str, datetime, int]:
        token_hash = hash_token(refresh_token_plaintext)
        token_candidate = await self.token_repo.get_by_hash(token_hash)

        if token_candidate is None or token_candidate.token_type != TOKEN_TYPE_REFRESH:
            raise HTTPException(status_code=_ERR_401, detail="Geçersiz oturum")

        demo_sandbox = await get_demo_sandbox_for_user(
            self.db,
            token_candidate.user_id,
            lock=True,
        )
        db_token = await self.token_repo.get_by_hash(token_hash, lock=True)
        if db_token is None or db_token.token_type != TOKEN_TYPE_REFRESH:
            raise HTTPException(status_code=_ERR_401, detail="Geçersiz oturum")

        if db_token.revoked_at is not None:
            await self.token_repo.revoke_family(db_token.token_family)
            await self.db.commit()
            raise HTTPException(status_code=_ERR_401, detail="Oturum zaten sonlandırıldı")

        if not self.token_repo.is_valid(db_token):
            raise HTTPException(status_code=_ERR_401, detail="Oturum süresi doldu")

        user = await self.db.scalar(
            select(User)
            .where(User.id == db_token.user_id, User.deleted_at.is_(None))
            .with_for_update()
        )
        if user is None or not user.is_active or user.is_deleted:
            raise HTTPException(status_code=_ERR_401, detail="Kullanıcı bulunamadı")
        await ensure_demo_user_access(
            self.db,
            user.id,
            str(db_token.token_family) if demo_sandbox is not None else None,
        )

        await self.token_repo.revoke(db_token)

        now = datetime.now(UTC)
        access_expires_at = now + timedelta(minutes=get_access_token_expire_minutes(user.user_type))
        refresh_expires_at = get_refresh_token_expires(user.user_type)
        extra_claims = {"user_type": user.user_type}
        if demo_sandbox is not None:
            access_expires_at = min(access_expires_at, demo_sandbox.expires_at)
            refresh_expires_at = min(refresh_expires_at, demo_sandbox.expires_at)
            extra_claims["demo"] = True
            extra_claims["demo_session_id"] = str(db_token.token_family)
        new_access_token = create_access_token(
            subject=str(user.id),
            extra_claims=extra_claims,
            expires_at=access_expires_at,
        )

        new_refresh_plaintext = generate_token()
        await self.token_repo.create(
            user_id=user.id,
            token_hash=hash_token(new_refresh_plaintext),
            token_family=db_token.token_family,
            token_type=TOKEN_TYPE_REFRESH,
            expires_at=refresh_expires_at,
            ip_address=ip,
            user_agent=user_agent,
        )
        await self.db.commit()

        expires_in = max(1, int((access_expires_at - now).total_seconds()))
        return (
            new_access_token,
            new_refresh_plaintext,
            user.user_type,
            refresh_expires_at,
            expires_in,
        )

    async def logout(self, refresh_token_plaintext: str) -> None:
        token_hash = hash_token(refresh_token_plaintext)
        db_token = await self.token_repo.get_by_hash(token_hash)
        if db_token and db_token.revoked_at is None:
            await self.token_repo.revoke(db_token)
            await self.db.commit()

    async def verify_email(self, data: EmailVerifyRequest) -> None:
        token_hash = hash_token(data.token)
        db_token = await self.token_repo.get_by_hash(token_hash)

        if db_token is None or db_token.token_type != TOKEN_TYPE_EMAIL_VERIFY:
            raise HTTPException(status_code=_ERR_400, detail="Geçersiz doğrulama kodu")

        if not self.token_repo.is_valid(db_token):
            raise HTTPException(status_code=_ERR_400, detail="Doğrulama kodunun süresi doldu")

        user = await self.user_repo.get_by_id(db_token.user_id)
        if user is None:
            raise HTTPException(status_code=_ERR_400, detail="Kullanıcı bulunamadı")

        user.is_verified = True
        self.db.add(user)
        await self.token_repo.revoke(db_token)
        await self.db.commit()

    async def resend_verification(self, data: ResendVerificationRequest) -> None:
        user = await self.user_repo.get_by_email(data.email)
        if user is None or user.is_deleted or user.is_verified:
            return

        await self.token_repo.revoke_all_for_user(user.id, TOKEN_TYPE_EMAIL_VERIFY)

        token_plaintext = generate_token()
        await self.token_repo.create(
            user_id=user.id,
            token_hash=hash_token(token_plaintext),
            token_family=new_token_family(),
            token_type=TOKEN_TYPE_EMAIL_VERIFY,
            expires_at=get_email_verify_expires(),
        )
        await self.db.commit()

        await email_service.send_verification_email(
            self.db, user.email, user.full_name, token_plaintext, user.locale
        )

    async def forgot_password(self, data: PasswordResetRequest) -> None:
        user = await self.user_repo.get_by_email(data.email)
        if user is None or user.is_deleted or not user.is_active:
            return

        await self.token_repo.revoke_all_for_user(user.id, TOKEN_TYPE_PASSWORD_RESET)

        token_plaintext = generate_token()
        await self.token_repo.create(
            user_id=user.id,
            token_hash=hash_token(token_plaintext),
            token_family=new_token_family(),
            token_type=TOKEN_TYPE_PASSWORD_RESET,
            expires_at=get_password_reset_expires(),
        )
        await self.db.commit()

        await email_service.send_password_reset_email(
            self.db, user.email, user.full_name, token_plaintext, user.locale
        )

    async def reset_password(self, data: PasswordResetConfirm) -> None:
        token_hash = hash_token(data.token)
        db_token = await self.token_repo.get_by_hash(token_hash)

        if db_token is None or db_token.token_type != TOKEN_TYPE_PASSWORD_RESET:
            raise HTTPException(status_code=_ERR_400, detail="Geçersiz sıfırlama kodu")

        if not self.token_repo.is_valid(db_token):
            raise HTTPException(status_code=_ERR_400, detail="Sıfırlama kodunun süresi doldu")

        user = await self.user_repo.get_by_id(db_token.user_id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=_ERR_400, detail="Kullanıcı bulunamadı")

        user.password_hash = hash_password(data.new_password)
        self.db.add(user)

        await self.token_repo.revoke(db_token)
        await self.token_repo.revoke_all_for_user(user.id, TOKEN_TYPE_REFRESH)
        await self.db.commit()

    async def change_password(self, user: User, data: ChangePasswordRequest) -> None:
        if not verify_password(data.current_password, user.password_hash):
            raise HTTPException(
                status_code=_ERR_400,
                detail="Mevcut şifre hatalı",
            )
        if verify_password(data.new_password, user.password_hash):
            raise HTTPException(
                status_code=_ERR_400,
                detail="Yeni şifre mevcut şifreyle aynı olamaz",
            )

        user.password_hash = hash_password(data.new_password)
        self.db.add(user)
        await self.token_repo.revoke_all_for_user(user.id, TOKEN_TYPE_REFRESH)
        await self.db.commit()

    def _build_token_response(
        self, user: User, access_token: str, extra: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        expire_minutes = get_access_token_expire_minutes(user.user_type)
        result: dict[str, Any] = {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": expire_minutes * 60,
            "mfa_required": False,
        }
        if extra:
            result.update(extra)
        return result


async def get_auth_service(db: AsyncSession) -> AuthService:
    return AuthService(db)

import uuid
from datetime import UTC, datetime

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import get_current_user, require_verified
from app.core.config import settings
from app.core.rate_limiter import (
    get_client_ip,
    rate_limit_login,
    rate_limit_password_reset,
    reset_login_rate_limit,
)
from app.db.session import get_db
from app.models.activity import ActivityLog
from app.models.enums import UserType
from app.models.user import User
from app.models.user_token import UserToken
from app.repositories.platform_audit_log import PlatformAuditLogRepository
from app.repositories.user_token import UserTokenRepository
from app.schemas.auth import (
    ChangePasswordRequest,
    EmailVerifyRequest,
    LoginRequest,
    MeResponse,
    MessageResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshResponse,
    RegisterRequest,
    ResendVerificationRequest,
    TokenResponse,
    UserProfileUpdate,
)
from app.schemas.platform import (
    MfaConfirmRequest,
    MfaConfirmResponse,
    MfaDisableRequest,
    MfaRegenerateRequest,
    MfaSetupResponse,
)
from app.schemas.session import SessionRead
from app.schemas.user import UserRead
from app.services.auth_service import AuthService
from app.services.mfa_service import MfaService
from app.services.storage_service import get_storage_backend, normalize_filename
from app.services.token_service import TOKEN_TYPE_REFRESH, get_access_token_expire_minutes

auth_router = APIRouter(prefix="/auth", tags=["auth"])

_AVATAR_ALLOWED = {"image/png", "image/jpeg", "image/webp"}
_AVATAR_MAX_BYTES = 5 * 1024 * 1024

_REFRESH_COOKIE = "refresh_token"
_REFRESH_COOKIE_PATH = "/api/v1/auth"


def set_refresh_cookie(
    response: Response,
    token: str,
    user_type: str,
    expires_at: datetime | None = None,
) -> None:
    if expires_at is not None:
        max_age = max(1, int((expires_at - datetime.now(UTC)).total_seconds()))
    else:
        max_age = (
            settings.PLATFORM_ADMIN_REFRESH_TOKEN_EXPIRE_HOURS * 3600
            if user_type == "platform_admin"
            else settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
        )
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=max_age,
        path=_REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_REFRESH_COOKIE, path=_REFRESH_COOKIE_PATH)


@auth_router.post("/register", response_model=UserRead, status_code=201)
async def register(
    data: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    svc = AuthService(db)
    return await svc.register(
        data,
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


@auth_router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(rate_limit_login),
) -> TokenResponse:
    svc = AuthService(db)
    user, access_token, refresh_token = await svc.login(
        data,
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await reset_login_rate_limit(request, data.email)
    set_refresh_cookie(response, refresh_token, user.user_type)
    return TokenResponse(
        access_token=access_token,
        expires_in=get_access_token_expire_minutes(user.user_type) * 60,
        mfa_required=False,
    )


@auth_router.post("/refresh", response_model=RefreshResponse)
async def refresh_tokens(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    cookie_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
) -> RefreshResponse:
    if not cookie_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Oturum bulunamadı",
        )
    svc = AuthService(db)
    new_access, new_refresh, user_type, refresh_expires_at, expires_in = await svc.refresh_tokens(
        cookie_token,
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    set_refresh_cookie(response, new_refresh, user_type, refresh_expires_at)
    return RefreshResponse(
        access_token=new_access,
        expires_in=expires_in,
    )


@auth_router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    cookie_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
) -> MessageResponse:
    if cookie_token:
        svc = AuthService(db)
        await svc.logout(cookie_token)
    _clear_refresh_cookie(response)
    return MessageResponse(message="Çıkış yapıldı")


@auth_router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@auth_router.patch("/me", response_model=MeResponse)
async def update_me(
    data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    from datetime import UTC, datetime

    if data.full_name is not None:
        current_user.full_name = data.full_name
    if data.job_title is not None:
        current_user.job_title = data.job_title or None
    if data.phone_number is not None:
        current_user.phone_number = data.phone_number or None
    if data.locale is not None:
        current_user.locale = data.locale
    if data.whatsapp_opt_in is not None:
        now = datetime.now(UTC)
        if data.whatsapp_opt_in and not current_user.whatsapp_opt_in:
            current_user.whatsapp_opt_in = True
            current_user.whatsapp_opt_in_at = now
            current_user.whatsapp_opt_out_at = None
        elif not data.whatsapp_opt_in and current_user.whatsapp_opt_in:
            current_user.whatsapp_opt_in = False
            current_user.whatsapp_opt_out_at = now
    await db.commit()
    await db.refresh(current_user)
    return current_user


@auth_router.post("/me/avatar", response_model=MeResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    ct = file.content_type or ""
    if ct not in _AVATAR_ALLOWED:
        raise HTTPException(
            status_code=422,
            detail="Yalnızca PNG, JPEG veya WebP yüklenebilir.",
        )
    data = await file.read()
    if len(data) > _AVATAR_MAX_BYTES:
        raise HTTPException(status_code=422, detail="Profil resmi 5 MB'ı aşamaz.")
    ext = normalize_filename(file.filename or "avatar.png").rsplit(".", 1)[-1]
    storage_key = f"user-avatars/{current_user.id}/avatar.{ext}"
    await get_storage_backend().save(data, storage_key)
    current_user.avatar_url = f"/media/{storage_key}"
    await db.commit()
    await db.refresh(current_user)
    return current_user


@auth_router.delete("/me/avatar", response_model=MeResponse)
async def delete_avatar(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    current_user.avatar_url = None
    await db.commit()
    await db.refresh(current_user)
    return current_user


@auth_router.post("/change-password", response_model=MessageResponse)
async def change_password(
    data: ChangePasswordRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    if current_user.user_type == "platform_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform yöneticileri platform parola endpointini kullanmalıdır",
        )

    svc = AuthService(db)
    await svc.change_password(current_user, data)
    _clear_refresh_cookie(response)
    return MessageResponse(message="Şifreniz güncellendi. Lütfen yeniden giriş yapın.")


@auth_router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    data: EmailVerifyRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    svc = AuthService(db)
    await svc.verify_email(data)
    return MessageResponse(message="E-posta adresiniz doğrulandı")


@auth_router.post("/verify-email/resend", response_model=MessageResponse)
async def resend_verification(
    data: ResendVerificationRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    svc = AuthService(db)
    await svc.resend_verification(data)
    return MessageResponse(message="Doğrulama e-postası gönderildi")


@auth_router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(rate_limit_password_reset),
) -> MessageResponse:
    svc = AuthService(db)
    await svc.forgot_password(data)
    return MessageResponse(message="Şifre sıfırlama bağlantısı gönderildi")


@auth_router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    svc = AuthService(db)
    await svc.reset_password(data)
    return MessageResponse(message="Şifreniz başarıyla güncellendi")


@auth_router.get("/me/verified", response_model=MeResponse)
async def me_verified(current_user: User = Depends(require_verified)) -> User:
    return current_user


# ── MFA setup endpoints ───────────────────────────────────────────────────────

mfa_router = APIRouter(prefix="/mfa", tags=["mfa"])


@mfa_router.post("/setup", response_model=MfaSetupResponse)
async def mfa_setup_begin(
    current_user: User = Depends(require_verified),
    db: AsyncSession = Depends(get_db),
) -> MfaSetupResponse:
    """Generate TOTP secret and QR URL. MFA is not enabled until /setup/confirm."""
    svc = MfaService(db)
    secret, otpauth_url = await svc.begin_setup(current_user)
    await db.commit()
    return MfaSetupResponse(secret=secret, otpauth_url=otpauth_url)


@mfa_router.post("/setup/confirm", response_model=MfaConfirmResponse)
async def mfa_setup_confirm(
    data: MfaConfirmRequest,
    current_user: User = Depends(require_verified),
    db: AsyncSession = Depends(get_db),
) -> MfaConfirmResponse:
    """Verify TOTP code from authenticator app, enable MFA, return recovery codes (shown once)."""
    svc = MfaService(db)
    codes = await svc.confirm_setup(current_user, data.code)
    await db.commit()
    return MfaConfirmResponse(
        recovery_codes=codes,
        message="MFA enabled. Save these recovery codes — they will not be shown again.",
    )


@mfa_router.post("/disable", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def mfa_disable(
    data: MfaDisableRequest,
    current_user: User = Depends(require_verified),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Disable MFA after verifying the current TOTP code."""
    svc = MfaService(db)
    await svc.disable(current_user, data.code)
    await db.commit()


@mfa_router.post("/recovery-codes/regenerate", response_model=MfaConfirmResponse)
async def mfa_regenerate_codes(
    data: MfaRegenerateRequest,
    current_user: User = Depends(require_verified),
    db: AsyncSession = Depends(get_db),
) -> MfaConfirmResponse:
    """Regenerate all recovery codes after verifying current TOTP."""
    svc = MfaService(db)
    codes = await svc.regenerate_recovery_codes(current_user, data.code)
    await db.commit()
    return MfaConfirmResponse(
        recovery_codes=codes,
        message="Recovery codes regenerated. Previous codes are now invalid.",
    )


# ── Active sessions (own account) ─────────────────────────────────────────────

sessions_router = APIRouter(prefix="/sessions", tags=["sessions"])


async def _write_audit(
    db: AsyncSession, actor: User, action: str, request: Request, meta: dict | None = None
) -> None:
    ip = get_client_ip(request)
    ua = request.headers.get("user-agent")
    if actor.user_type == UserType.PLATFORM_ADMIN.value:
        await PlatformAuditLogRepository(db).create(
            admin_user_id=actor.id,
            action=action,
            target_type="user_session",
            target_id=actor.id,
            ip_address=ip,
            user_agent=ua,
            meta=meta,
        )
    else:
        db.add(
            ActivityLog(
                actor_user_id=actor.id,
                action=action,
                entity_type="user_session",
                entity_id=actor.id,
                ip_address=ip,
                user_agent=ua,
                meta=meta,
            )
        )


@sessions_router.get("", response_model=list[SessionRead])
async def list_sessions(
    current_user: User = Depends(require_verified),
    db: AsyncSession = Depends(get_db),
) -> list[SessionRead]:
    """List this account's active (non-revoked, non-expired) refresh-token sessions."""
    result = await db.execute(
        select(UserToken)
        .where(
            UserToken.user_id == current_user.id,
            UserToken.token_type == TOKEN_TYPE_REFRESH,
            UserToken.revoked_at.is_(None),
        )
        .order_by(UserToken.created_at.desc())
    )
    tokens = result.scalars().all()
    now = datetime.now(UTC)
    return [SessionRead.model_validate(t) for t in tokens if t.expires_at.replace(tzinfo=UTC) > now]


@sessions_router.delete(
    "/{session_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
async def revoke_session(
    session_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_verified),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke one of this account's own sessions. Cannot target other users' tokens."""
    result = await db.execute(
        select(UserToken).where(
            UserToken.id == session_id,
            UserToken.user_id == current_user.id,
        )
    )
    token = result.scalar_one_or_none()
    if token is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    repo = UserTokenRepository(db)
    await repo.revoke(token)
    await _write_audit(
        db, current_user, "user.session_revoked", request, {"session_id": str(token.id)}
    )
    await db.commit()


@sessions_router.post("/revoke-all", response_model=MessageResponse)
async def revoke_all_sessions(
    request: Request,
    current_user: User = Depends(require_verified),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Revoke every active session for this account, including the one used to call this
    endpoint — the caller will need to log in again. There is no reliable way to identify
    "this browser's" refresh token from an access-token-authenticated request, so this is
    an all-or-nothing sign-out rather than a selective "others only" revoke."""
    repo = UserTokenRepository(db)
    await repo.revoke_all_for_user(current_user.id, token_type=TOKEN_TYPE_REFRESH)
    await _write_audit(db, current_user, "user.all_sessions_revoked", request)
    await db.commit()
    return MessageResponse(message="Tüm oturumlar kapatıldı. Lütfen yeniden giriş yapın.")


auth_router.include_router(sessions_router)
auth_router.include_router(mfa_router)

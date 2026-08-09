"""Platform admin authentication endpoints with MFA support."""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_platform_admin_user
from app.core.rate_limiter import (
    enforce_platform_ip_allowlist,
    get_client_ip,
    rate_limit_platform_login,
    rate_limit_platform_mfa_recovery,
    rate_limit_platform_mfa_verify,
    reset_platform_login_rate_limit,
)
from app.core.security import (
    create_access_token,
    create_mfa_session_token,
    decode_mfa_session_token,
)
from app.db.session import get_db
from app.models.enums import UserType
from app.models.user import User
from app.repositories.platform_audit_log import PlatformAuditLogRepository
from app.repositories.user_token import UserTokenRepository
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshResponse,
    TokenResponse,
)
from app.schemas.platform import MfaRecoveryRequest, MfaVerifyRequest
from app.services.auth_service import AuthService
from app.services.mfa_service import MfaService
from app.services.token_service import (
    TOKEN_TYPE_REFRESH,
    generate_token,
    get_access_token_expire_minutes,
    get_refresh_token_expires,
    hash_token,
    new_token_family,
)

platform_auth_router = APIRouter(prefix="/auth", tags=["platform-auth"])

_REFRESH_COOKIE = "platform_refresh_token"
_REFRESH_COOKIE_PATH = "/api/v1/platform/auth"


def _set_platform_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.is_production,
        # Frontend and API are hosted on different sites in production.
        # Cross-site refresh cookies require SameSite=None together with Secure.
        samesite="none" if settings.is_production else "lax",
        max_age=settings.PLATFORM_ADMIN_REFRESH_TOKEN_EXPIRE_HOURS * 3600,
        path=_REFRESH_COOKIE_PATH,
    )


def _clear_platform_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_REFRESH_COOKIE, path=_REFRESH_COOKIE_PATH)


async def _issue_full_tokens(
    user: User,
    db: AsyncSession,
    response: Response,
    ip: str | None,
    user_agent: str | None,
) -> TokenResponse:
    """Create and persist access + refresh tokens; set cookie; write audit log."""
    expire_minutes = get_access_token_expire_minutes(user.user_type)
    access_token = create_access_token(
        subject=str(user.id),
        extra_claims={"user_type": user.user_type},
        expire_minutes=expire_minutes,
    )

    refresh_plaintext = generate_token()
    token_repo = UserTokenRepository(db)
    await token_repo.create(
        user_id=user.id,
        token_hash=hash_token(refresh_plaintext),
        token_family=new_token_family(),
        token_type=TOKEN_TYPE_REFRESH,
        expires_at=get_refresh_token_expires(user.user_type),
        ip_address=ip,
        user_agent=user_agent,
    )

    audit_repo = PlatformAuditLogRepository(db)
    await audit_repo.create(
        admin_user_id=user.id,
        action="platform_admin.login",
        ip_address=ip,
        user_agent=user_agent,
    )
    await db.commit()

    _set_platform_refresh_cookie(response, refresh_plaintext)
    return TokenResponse(
        access_token=access_token,
        expires_in=expire_minutes * 60,
        mfa_required=False,
    )


@platform_auth_router.post("/login", response_model=TokenResponse)
async def platform_admin_login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _ip_allowlist: None = Depends(enforce_platform_ip_allowlist),
    _rate_limit: None = Depends(rate_limit_platform_login),
) -> TokenResponse:
    ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent")
    svc = AuthService(db)
    user = await svc.platform_admin_login(data, ip=ip, user_agent=user_agent)
    await reset_platform_login_rate_limit(request, data.email)

    # If MFA is enabled, return a short-lived session token instead of full access
    if user.mfa_enabled and user.mfa_secret_encrypted:
        mfa_token = create_mfa_session_token(str(user.id))
        return TokenResponse(
            access_token="",
            expires_in=0,
            mfa_required=True,
            mfa_session_token=mfa_token,
        )

    # No MFA — issue full tokens (also writes audit log + commits)
    return await _issue_full_tokens(
        user=user,
        db=db,
        response=response,
        ip=ip,
        user_agent=user_agent,
    )


@platform_auth_router.post("/change-password", response_model=MessageResponse)
async def platform_change_password(
    data: ChangePasswordRequest,
    response: Response,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    svc = AuthService(db)
    await svc.change_password(admin, data)
    _clear_platform_refresh_cookie(response)
    return MessageResponse(message="Şifreniz güncellendi. Lütfen yeniden giriş yapın.")


@platform_auth_router.post("/mfa-verify", response_model=TokenResponse)
async def platform_mfa_verify(
    data: MfaVerifyRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _ip_allowlist: None = Depends(enforce_platform_ip_allowlist),
    _rate_limit: None = Depends(rate_limit_platform_mfa_verify),
) -> TokenResponse:
    """Step 2 of MFA login: verify TOTP code and issue full tokens."""
    try:
        payload = decode_mfa_session_token(data.mfa_session_token)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired MFA session",
        ) from err

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or user.user_type != UserType.PLATFORM_ADMIN.value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    mfa_svc = MfaService(db)
    if not await mfa_svc.verify_code(user, data.code):
        audit_repo = PlatformAuditLogRepository(db)
        await audit_repo.create(
            admin_user_id=user.id,
            action="platform_admin.mfa_verify_failed",
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
        await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid TOTP code")

    return await _issue_full_tokens(
        user=user,
        db=db,
        response=response,
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


@platform_auth_router.post("/mfa-recovery", response_model=TokenResponse)
async def platform_mfa_recovery(
    data: MfaRecoveryRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _ip_allowlist: None = Depends(enforce_platform_ip_allowlist),
    _rate_limit: None = Depends(rate_limit_platform_mfa_recovery),
) -> TokenResponse:
    """MFA login using a recovery code instead of TOTP."""
    try:
        payload = decode_mfa_session_token(data.mfa_session_token)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired MFA session",
        ) from err

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or user.user_type != UserType.PLATFORM_ADMIN.value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    mfa_svc = MfaService(db)
    if not await mfa_svc.use_recovery_code(user, data.recovery_code):
        raise HTTPException(status_code=400, detail="Invalid or already-used recovery code")

    return await _issue_full_tokens(
        user=user,
        db=db,
        response=response,
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


@platform_auth_router.post("/logout", response_model=MessageResponse)
async def platform_logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    cookie_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
) -> MessageResponse:
    if cookie_token:
        svc = AuthService(db)
        await svc.logout(cookie_token)
    _clear_platform_refresh_cookie(response)
    return MessageResponse(message="Çıkış yapıldı")


@platform_auth_router.post("/refresh", response_model=RefreshResponse)
async def platform_refresh_token(
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
    new_access, new_refresh, user_type = await svc.refresh_tokens(
        cookie_token,
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    if user_type != UserType.PLATFORM_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin access required",
        )
    _set_platform_refresh_cookie(response, new_refresh)
    return RefreshResponse(
        access_token=new_access,
        expires_in=get_access_token_expire_minutes(user_type) * 60,
    )

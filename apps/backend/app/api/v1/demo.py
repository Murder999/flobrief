from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import get_current_user
from app.core.config import settings
from app.core.rate_limiter import get_client_ip
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.brand import Brand
from app.models.brand_member import BrandMember
from app.models.demo_sandbox import DemoSandbox
from app.models.enums import (
    AgencyMemberStatus,
    AgencyStatus,
    BrandMemberStatus,
    UserType,
)
from app.models.user import User
from app.models.user_token import UserToken
from app.schemas.demo_sandbox import (
    DemoPortalSwitchRequest,
    DemoPortalSwitchResponse,
    DemoPublicStatus,
    DemoSessionStatus,
    DemoStartRequest,
    DemoStartResponse,
)
from app.services.demo_access import get_demo_sandbox_for_user
from app.services.demo_sandbox_service import DemoSandboxService, demo_counts, get_demo_settings
from app.services.token_service import (
    TOKEN_TYPE_REFRESH,
    generate_token,
    hash_token,
    new_token_family,
)

demo_router = APIRouter(prefix="/demo", tags=["public-demo"])
_REFRESH_COOKIE_PATH = "/api/v1/auth"


def _set_demo_refresh_cookie(
    response: Response,
    token: str,
    expires_at: datetime,
) -> None:
    max_age = max(1, int((expires_at - datetime.now(UTC)).total_seconds()))
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=max_age,
        path=_REFRESH_COOKIE_PATH,
    )


async def _identity_has_active_membership(
    db: AsyncSession,
    sandbox: DemoSandbox,
    user: User,
    portal: str,
) -> bool:
    if portal == "agency":
        if user.id != sandbox.owner_user_id or user.user_type != UserType.AGENCY_USER.value:
            return False
        membership = await db.scalar(
            select(AgencyMember.id).where(
                AgencyMember.agency_id == sandbox.agency_id,
                AgencyMember.user_id == user.id,
                AgencyMember.status == AgencyMemberStatus.ACTIVE.value,
                AgencyMember.deleted_at.is_(None),
            )
        )
        return membership is not None

    if user.id != sandbox.brand_user_id or user.user_type != UserType.BRAND_USER.value:
        return False
    membership = await db.scalar(
        select(BrandMember.id)
        .join(Brand, Brand.id == BrandMember.brand_id)
        .where(
            BrandMember.user_id == user.id,
            BrandMember.status == BrandMemberStatus.ACTIVE.value,
            BrandMember.deleted_at.is_(None),
            Brand.agency_id == sandbox.agency_id,
            Brand.deleted_at.is_(None),
        )
    )
    return membership is not None


@demo_router.get("/status", response_model=DemoPublicStatus)
async def demo_status(db: AsyncSession = Depends(get_db)) -> DemoPublicStatus:
    config = await get_demo_settings(db)
    active, _, _ = await demo_counts(db)
    enabled = bool(config and config.enabled)
    duration = config.duration_hours if config else 4
    capacity = config.max_active_sandboxes if config else 20
    captcha_required = config.captcha_required if config else True
    captcha_configured = bool(
        settings.DEMO_SANDBOX_TURNSTILE_SITE_KEY and settings.DEMO_SANDBOX_TURNSTILE_SECRET_KEY
    )
    available = enabled and active < capacity and (not captcha_required or captcha_configured)
    reason = None
    if not enabled:
        reason = "Demo sandbox şu anda kapalı."
    elif active >= capacity:
        reason = "Demo kapasitesi şu anda dolu."
    elif captcha_required and not captcha_configured:
        reason = "Demo güvenlik doğrulaması henüz yapılandırılmadı."
    return DemoPublicStatus(
        enabled=enabled,
        available=available,
        unavailable_reason=reason,
        duration_hours=duration,
        captcha_required=captcha_required,
        captcha_site_key=(
            settings.DEMO_SANDBOX_TURNSTILE_SITE_KEY
            if captcha_required and captcha_configured
            else None
        ),
        active_sandboxes=active,
        capacity=capacity,
    )


@demo_router.post(
    "/sandboxes",
    response_model=DemoStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_demo_sandbox(
    body: DemoStartRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> DemoStartResponse:
    service = DemoSandboxService(db)
    sandbox, access_token, refresh_token = await service.create(
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        turnstile_token=body.turnstile_token,
    )
    ttl_seconds = max(
        1,
        int((sandbox.expires_at - sandbox.created_at).total_seconds()),
    )
    _set_demo_refresh_cookie(response, refresh_token, sandbox.expires_at)
    return DemoStartResponse(
        access_token=access_token,
        expires_in=min(settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, ttl_seconds),
        agency_id=sandbox.agency_id,
        expires_at=sandbox.expires_at,
    )


@demo_router.get("/session", response_model=DemoSessionStatus)
async def demo_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DemoSessionStatus:
    """Get current demo session status and active portal."""
    sandbox = await get_demo_sandbox_for_user(db, current_user.id)
    if sandbox is None:
        return DemoSessionStatus(is_demo=False, active_portal=None, expires_at=None)

    agency = await db.get(Agency, sandbox.agency_id)
    now = datetime.now(UTC)
    is_active = (
        sandbox.status == "active"
        and sandbox.expires_at > now
        and agency is not None
        and agency.is_demo
        and agency.status == AgencyStatus.ACTIVE.value
        and agency.demo_expires_at is not None
        and agency.demo_expires_at > now
    )
    active_portal = "agency" if current_user.id == sandbox.owner_user_id else "brand"
    if is_active and not await _identity_has_active_membership(
        db, sandbox, current_user, active_portal
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Demo kimliği artık geçerli değil")

    return DemoSessionStatus(
        is_demo=is_active,
        active_portal=active_portal if is_active else None,
        expires_at=sandbox.expires_at.isoformat() if is_active else None,
    )


@demo_router.post("/switch-portal", response_model=DemoPortalSwitchResponse)
async def demo_switch_portal(
    body: DemoPortalSwitchRequest,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DemoPortalSwitchResponse:
    """Replace the current demo identity with the paired portal identity."""
    sandbox = await get_demo_sandbox_for_user(db, current_user.id, lock=True)
    if sandbox is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo portal switch only available in demo mode",
        )

    agency = await db.get(Agency, sandbox.agency_id)
    now = datetime.now(UTC)
    if (
        sandbox.status != "active"
        or sandbox.expires_at <= now
        or agency is None
        or not agency.is_demo
        or agency.status != AgencyStatus.ACTIVE.value
        or agency.demo_expires_at is None
        or agency.demo_expires_at <= now
    ):
        if sandbox.status == "active":
            await DemoSandboxService(db).terminate(sandbox, reason="expired")
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Demo session expired",
        )

    identity_ids = [sandbox.owner_user_id]
    if sandbox.brand_user_id is not None:
        identity_ids.append(sandbox.brand_user_id)
    identity_users = list(
        (
            await db.execute(
                select(User)
                .where(User.id.in_(identity_ids), User.deleted_at.is_(None))
                .order_by(User.id)
                .with_for_update()
            )
        ).scalars()
    )
    users_by_id = {user.id: user for user in identity_users}
    source_user = users_by_id.get(current_user.id)
    source_portal = "agency" if current_user.id == sandbox.owner_user_id else "brand"
    if (
        source_user is None
        or not source_user.is_active
        or not await _identity_has_active_membership(db, sandbox, source_user, source_portal)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo source identity is not active",
        )

    target_portal = body.portal
    target_user_id = sandbox.owner_user_id if target_portal == "agency" else sandbox.brand_user_id
    target_user = users_by_id.get(target_user_id) if target_user_id is not None else None
    if (
        target_user is None
        or not target_user.is_verified
        or not await _identity_has_active_membership(db, sandbox, target_user, target_portal)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo target identity is not active",
        )

    for identity_user in identity_users:
        identity_user.is_active = identity_user.id == target_user.id
        db.add(identity_user)
    await db.execute(
        update(UserToken)
        .where(
            UserToken.user_id.in_(identity_ids),
            UserToken.token_type == TOKEN_TYPE_REFRESH,
            UserToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    refresh_token = generate_token()
    token_family = new_token_family()
    db.add(
        UserToken(
            user_id=target_user.id,
            token_hash=hash_token(refresh_token),
            token_family=token_family,
            token_type=TOKEN_TYPE_REFRESH,
            expires_at=sandbox.expires_at,
            ip_address=get_client_ip(request),
            user_agent=(request.headers.get("user-agent") or "")[:1000] or None,
        )
    )
    target_user.last_login_at = now
    db.add(target_user)

    access_expires_at = min(
        now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        sandbox.expires_at,
    )
    access_token = create_access_token(
        subject=str(target_user.id),
        extra_claims={
            "user_type": target_user.user_type,
            "demo": True,
            "demo_session_id": str(token_family),
        },
        expires_at=access_expires_at,
    )
    await db.commit()

    _set_demo_refresh_cookie(response, refresh_token, sandbox.expires_at)
    redirect_to = "/dashboard" if target_portal == "agency" else "/brand/dashboard"

    return DemoPortalSwitchResponse(
        portal=target_portal,
        redirect_to=redirect_to,
        expires_at=sandbox.expires_at.isoformat(),
        access_token=access_token,
        expires_in=max(1, int((access_expires_at - now).total_seconds())),
    )

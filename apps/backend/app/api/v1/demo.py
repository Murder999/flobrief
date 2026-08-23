from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import get_current_user
from app.core.config import settings
from app.core.rate_limiter import get_client_ip
from app.db.session import get_db
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.brand import Brand
from app.models.user import User
from app.schemas.demo_sandbox import (
    DemoPortalSwitchRequest,
    DemoPortalSwitchResponse,
    DemoPublicStatus,
    DemoSessionStatus,
    DemoStartRequest,
    DemoStartResponse,
)
from app.services.demo_sandbox_service import DemoSandboxService, demo_counts, get_demo_settings

demo_router = APIRouter(prefix="/demo", tags=["public-demo"])


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
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=ttl_seconds,
        path="/api/v1/auth",
    )
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
    # Check if user is in a demo agency
    agency = await db.scalar(
        select(Agency)
        .join(AgencyMember, AgencyMember.agency_id == Agency.id)
        .where(
            AgencyMember.user_id == current_user.id,
            AgencyMember.deleted_at.is_(None),
            Agency.is_demo.is_(True),
            Agency.deleted_at.is_(None),
        )
        .limit(1)
    )

    if agency is None:
        return DemoSessionStatus(is_demo=False, active_portal=None, expires_at=None)

    from datetime import UTC, datetime

    now = datetime.now(UTC)
    is_active = (
        agency.status == "active"
        and agency.demo_expires_at is not None
        and agency.demo_expires_at > now
    )

    # Determine active portal from request context or default to agency
    # For demo, we track active portal via a simple approach
    # The frontend will tell us which portal it's currently in
    # We can infer from the user's last activity or just return the agency as default
    active_portal = "agency"  # default

    return DemoSessionStatus(
        is_demo=is_active,
        active_portal=active_portal if is_active else None,
        expires_at=agency.demo_expires_at.isoformat() if agency.demo_expires_at else None,
    )


@demo_router.post("/switch-portal", response_model=DemoPortalSwitchResponse)
async def demo_switch_portal(
    body: DemoPortalSwitchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DemoPortalSwitchResponse:
    """Switch between agency and brand portal in demo mode."""
    # Verify user is in a demo agency
    agency = await db.scalar(
        select(Agency)
        .join(AgencyMember, AgencyMember.agency_id == Agency.id)
        .where(
            AgencyMember.user_id == current_user.id,
            AgencyMember.deleted_at.is_(None),
            Agency.is_demo.is_(True),
            Agency.deleted_at.is_(None),
        )
        .limit(1)
    )

    if agency is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo portal switch only available in demo mode",
        )

    from datetime import UTC, datetime

    now = datetime.now(UTC)
    if agency.status != "active" or agency.demo_expires_at is None or agency.demo_expires_at <= now:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Demo session expired",
        )

    target_portal = body.portal
    if target_portal not in ("agency", "brand"):
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid portal. Must be 'agency' or 'brand'",
        )

    # For brand portal, verify there's at least one brand in the demo agency
    if target_portal == "brand":
        brand = await db.scalar(
            select(Brand)
            .where(
                Brand.agency_id == agency.id,
                Brand.deleted_at.is_(None),
            )
            .limit(1)
        )
        if brand is None:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No brands available in demo agency",
            )

    # Determine redirect URL
    redirect_to = "/dashboard" if target_portal == "agency" else "/brand/dashboard"

    return DemoPortalSwitchResponse(
        portal=target_portal,
        redirect_to=redirect_to,
        expires_at=agency.demo_expires_at.isoformat() if agency.demo_expires_at else "",
    )

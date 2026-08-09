from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limiter import get_client_ip
from app.db.session import get_db
from app.schemas.demo_sandbox import DemoPublicStatus, DemoStartRequest, DemoStartResponse
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

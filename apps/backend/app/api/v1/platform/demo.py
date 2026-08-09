from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_platform_admin_user
from app.core.rate_limiter import get_client_ip
from app.db.session import get_db
from app.models.agency import Agency
from app.models.demo_sandbox import DemoSandbox
from app.models.user import User
from app.repositories.platform_audit_log import PlatformAuditLogRepository
from app.schemas.demo_sandbox import (
    DemoSandboxRead,
    DemoSettingsRead,
    DemoSettingsUpdate,
)
from app.services.demo_sandbox_service import (
    DemoSandboxService,
    demo_counts,
    get_demo_settings,
    terminate_expired_sandboxes,
)

platform_demo_router = APIRouter(prefix="/demo", tags=["platform-demo"])


async def _settings_read(db: AsyncSession) -> DemoSettingsRead:
    config = await get_demo_settings(db, create=True)
    assert config is not None
    active, total, inactive = await demo_counts(db)
    return DemoSettingsRead(
        enabled=config.enabled,
        duration_hours=config.duration_hours,
        max_active_sandboxes=config.max_active_sandboxes,
        max_creations_per_ip_per_day=config.max_creations_per_ip_per_day,
        captcha_required=config.captcha_required,
        captcha_configured=bool(
            settings.DEMO_SANDBOX_TURNSTILE_SITE_KEY and settings.DEMO_SANDBOX_TURNSTILE_SECRET_KEY
        ),
        active_sandboxes=active,
        total_created=total,
        expired_or_terminated=inactive,
    )


@platform_demo_router.get("/settings", response_model=DemoSettingsRead)
async def read_demo_settings(
    _admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> DemoSettingsRead:
    result = await _settings_read(db)
    await db.commit()
    return result


@platform_demo_router.patch("/settings", response_model=DemoSettingsRead)
async def update_demo_settings(
    body: DemoSettingsUpdate,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> DemoSettingsRead:
    config = await get_demo_settings(db, create=True, lock=True)
    assert config is not None
    changes = body.model_dump(exclude_unset=True)
    if (
        changes.get("enabled") is True
        and changes.get("captcha_required", config.captcha_required)
        and not (
            settings.DEMO_SANDBOX_TURNSTILE_SITE_KEY and settings.DEMO_SANDBOX_TURNSTILE_SECRET_KEY
        )
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "CAPTCHA zorunluyken Turnstile anahtarları olmadan demo açılamaz",
        )
    for field, value in changes.items():
        setattr(config, field, value)
    db.add(config)
    await PlatformAuditLogRepository(db).create(
        admin_user_id=admin.id,
        action="demo.settings_updated",
        target_type="demo_settings",
        target_id=None,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        meta=changes,
    )
    await db.commit()
    return await _settings_read(db)


@platform_demo_router.get("/sandboxes", response_model=list[DemoSandboxRead])
async def list_demo_sandboxes(
    status_filter: str | None = None,
    limit: int = 100,
    _admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[DemoSandboxRead]:
    if limit < 1 or limit > 500:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "limit 1-500 olmalı")
    stmt = (
        select(DemoSandbox, Agency)
        .join(Agency, Agency.id == DemoSandbox.agency_id)
        .where(DemoSandbox.deleted_at.is_(None))
        .order_by(DemoSandbox.created_at.desc())
        .limit(limit)
    )
    if status_filter:
        stmt = stmt.where(DemoSandbox.status == status_filter)
    rows = (await db.execute(stmt)).all()
    return [
        DemoSandboxRead(
            id=sandbox.id,
            agency_id=sandbox.agency_id,
            owner_user_id=sandbox.owner_user_id,
            agency_name=agency.name,
            status=sandbox.status,
            expires_at=sandbox.expires_at,
            terminated_at=sandbox.terminated_at,
            termination_reason=sandbox.termination_reason,
            created_at=sandbox.created_at,
        )
        for sandbox, agency in rows
    ]


@platform_demo_router.post(
    "/sandboxes/{sandbox_id}/terminate",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def terminate_demo_sandbox(
    sandbox_id: uuid.UUID,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    sandbox = await db.scalar(
        select(DemoSandbox)
        .where(DemoSandbox.id == sandbox_id, DemoSandbox.deleted_at.is_(None))
        .with_for_update()
    )
    if sandbox is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demo sandbox bulunamadı")
    await DemoSandboxService(db).terminate(sandbox, reason="platform_admin")
    await PlatformAuditLogRepository(db).create(
        admin_user_id=admin.id,
        action="demo.sandbox_terminated",
        target_type="demo_sandbox",
        target_id=sandbox.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        meta={"agency_id": str(sandbox.agency_id), "terminated_at": datetime.now(UTC).isoformat()},
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@platform_demo_router.post("/cleanup")
async def cleanup_demo_sandboxes(
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    cleaned = await terminate_expired_sandboxes(db)
    await PlatformAuditLogRepository(db).create(
        admin_user_id=admin.id,
        action="demo.cleanup_run",
        target_type="demo_sandbox",
        target_id=None,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        meta={"cleaned": cleaned},
    )
    await db.commit()
    return {"cleaned": cleaned}

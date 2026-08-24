from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.demo_sandbox import DemoSandbox
from app.models.enums import AgencyStatus
from app.models.user_token import UserToken
from app.services.token_service import TOKEN_TYPE_REFRESH

_BLOCKED_MUTATION_PREFIXES = (
    "/api/v1/invitations",
    "/api/v1/accounting-connectors",
    "/api/v1/payments",
)
_BLOCKED_MUTATION_PATHS = (
    "/api/v1/billing/checkout",
    "/api/v1/billing/cancel",
    "/api/v1/billing/change-plan",
    "/api/v1/brand-portal/team/invite",
)


async def get_demo_sandbox_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    lock: bool = False,
) -> DemoSandbox | None:
    stmt = (
        select(DemoSandbox)
        .where(
            or_(
                DemoSandbox.owner_user_id == user_id,
                DemoSandbox.brand_user_id == user_id,
            ),
            DemoSandbox.deleted_at.is_(None),
        )
        .limit(1)
    )
    if lock:
        stmt = stmt.with_for_update()
    return await db.scalar(stmt)


async def ensure_demo_user_access(
    db: AsyncSession,
    user_id: uuid.UUID,
    demo_session_id: str | None = None,
) -> None:
    """Reject a synthetic demo user immediately after its tenant expires."""
    sandbox = await get_demo_sandbox_for_user(db, user_id)
    if sandbox is not None:
        agency = await db.scalar(
            select(Agency).where(
                Agency.id == sandbox.agency_id,
                Agency.is_demo.is_(True),
                Agency.deleted_at.is_(None),
            )
        )
    else:
        sandbox = None
        agency = await db.scalar(
            select(Agency)
            .join(AgencyMember, AgencyMember.agency_id == Agency.id)
            .where(
                AgencyMember.user_id == user_id,
                AgencyMember.deleted_at.is_(None),
                Agency.is_demo.is_(True),
                Agency.deleted_at.is_(None),
            )
            .limit(1)
        )
    if agency is None:
        return
    now = datetime.now(UTC)
    if (
        (sandbox is not None and (sandbox.status != "active" or sandbox.expires_at <= now))
        or agency.status != AgencyStatus.ACTIVE.value
        or agency.demo_expires_at is None
        or agency.demo_expires_at <= now
    ):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Demo oturumunun süresi doldu",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if sandbox is not None:
        try:
            token_family = uuid.UUID(str(demo_session_id))
        except (TypeError, ValueError):
            token_family = None
        active_session = None
        if token_family is not None:
            active_session = await db.scalar(
                select(UserToken.id).where(
                    UserToken.user_id == user_id,
                    UserToken.token_family == token_family,
                    UserToken.token_type == TOKEN_TYPE_REFRESH,
                    UserToken.revoked_at.is_(None),
                    UserToken.expires_at > now,
                )
            )
        if active_session is None:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Demo oturumu artık aktif değil",
                headers={"WWW-Authenticate": "Bearer"},
            )


def enforce_demo_workspace_request(agency: Agency, request: Request) -> None:
    if not agency.is_demo:
        return
    now = datetime.now(UTC)
    if agency.demo_expires_at is None or agency.demo_expires_at <= now:
        raise HTTPException(status.HTTP_410_GONE, "Demo çalışma alanının süresi doldu")
    if agency.status != AgencyStatus.ACTIVE.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Demo çalışma alanı aktif değil")
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    path = request.url.path
    if path.startswith(_BLOCKED_MUTATION_PREFIXES) or path in _BLOCKED_MUTATION_PATHS:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Bu işlem güvenli demo ortamında kullanılamaz",
        )
    if path.startswith("/api/v1/brand-portal/team/invitations/") and path.endswith("/resend"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Bu işlem güvenli demo ortamında kullanılamaz",
        )
    if path.startswith("/api/v1/invoices/") and path.endswith("/send"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Demo ortamında dış fatura gönderimi kapalıdır",
        )

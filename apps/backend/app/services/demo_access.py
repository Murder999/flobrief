from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.enums import AgencyStatus

_BLOCKED_MUTATION_PREFIXES = (
    "/api/v1/invitations",
    "/api/v1/accounting-connectors",
    "/api/v1/payments",
)
_BLOCKED_MUTATION_PATHS = (
    "/api/v1/billing/checkout",
    "/api/v1/billing/cancel",
    "/api/v1/billing/change-plan",
)


async def ensure_demo_user_access(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> None:
    """Reject a synthetic demo user immediately after its tenant expires."""
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
        agency.status != AgencyStatus.ACTIVE.value
        or agency.demo_expires_at is None
        or agency.demo_expires_at <= now
    ):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Demo oturumunun süresi doldu",
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
    if path.startswith("/api/v1/invoices/") and path.endswith("/send"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Demo ortamında dış fatura gönderimi kapalıdır",
        )

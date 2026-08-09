"""Platform admin — impersonation endpoints.

Impersonation is always transparent: logged to platform_audit_logs, and the
issued token carries is_impersonation=true and impersonator_id claims.
The frontend must display a visible banner when the flag is present.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_platform_admin_user
from app.core.impersonation_sessions import (
    end_impersonation_session,
    start_impersonation_session,
)
from app.core.rate_limiter import get_client_ip
from app.core.security import ALGORITHM
from app.db.session import get_db
from app.models.agency_member import AgencyMember
from app.models.user import User
from app.repositories.platform_audit_log import PlatformAuditLogRepository
from app.schemas.platform import ImpersonateStartRequest, ImpersonationResponse

platform_impersonate_router = APIRouter(prefix="/impersonate", tags=["platform-impersonate"])

_IMPERSONATION_TTL_SECONDS = 900  # 15 minutes — deliberately short-lived


def _create_impersonation_token(
    impersonated_user: User,
    agency_id: uuid.UUID | None,
    role: str | None,
    impersonator_id: uuid.UUID,
    jti: str,
) -> str:
    expire = datetime.now(UTC) + timedelta(seconds=_IMPERSONATION_TTL_SECONDS)
    payload = {
        "sub": str(impersonated_user.id),
        "user_type": impersonated_user.user_type,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(UTC),
        "is_impersonation": True,
        "impersonator_id": str(impersonator_id),
        "jti": jti,
    }
    if agency_id:
        payload["agency_id"] = str(agency_id)
    if role:
        payload["role"] = role
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


@platform_impersonate_router.post("/{user_id}", response_model=ImpersonationResponse)
async def start_impersonation(
    user_id: uuid.UUID,
    body: ImpersonateStartRequest,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> ImpersonationResponse:
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot impersonate yourself")

    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if target.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot impersonate another platform admin",
        )
    if not target.is_active:
        raise HTTPException(status_code=400, detail="Cannot impersonate an inactive user")

    # Get user's primary agency membership
    member_result = await db.execute(
        select(AgencyMember)
        .where(AgencyMember.user_id == user_id, AgencyMember.deleted_at.is_(None))
        .order_by(AgencyMember.created_at.asc())
        .limit(1)
    )
    member = member_result.scalar_one_or_none()
    agency_id = member.agency_id if member else None
    role = member.role if member else None

    jti = str(uuid.uuid4())
    token = _create_impersonation_token(target, agency_id, role, admin.id, jti)

    audit_repo = PlatformAuditLogRepository(db)
    await audit_repo.create(
        admin_user_id=admin.id,
        action="impersonation.started",
        target_type="user",
        target_id=user_id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        meta={
            "reason": body.reason,
            "impersonated_email": target.email,
            "agency_id": str(agency_id) if agency_id else None,
        },
    )

    # Starting a new session for this admin implicitly revokes any prior
    # impersonation token they still held (switching targets can't leave the
    # old token usable). If the session store is unreachable we must not
    # issue a token we can't guarantee is revocable.
    try:
        await start_impersonation_session(str(admin.id), jti, _IMPERSONATION_TTL_SECONDS)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Impersonation service temporarily unavailable",
        ) from err

    await db.commit()

    return ImpersonationResponse(
        access_token=token,
        expires_in=_IMPERSONATION_TTL_SECONDS,
        impersonated_user_id=str(target.id),
        impersonated_email=target.email,
        impersonated_user_type=target.user_type,
    )


@platform_impersonate_router.post(
    "/end", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
async def end_impersonation(
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke the admin's active impersonation session and log the end."""
    await end_impersonation_session(str(admin.id))
    audit_repo = PlatformAuditLogRepository(db)
    await audit_repo.create(
        admin_user_id=admin.id,
        action="impersonation.ended",
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()

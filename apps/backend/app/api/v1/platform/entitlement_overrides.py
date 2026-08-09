"""Platform admin — per-agency/per-brand entitlement limit overrides."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_platform_admin_user
from app.core.rate_limiter import get_client_ip
from app.db.session import get_db
from app.models.entitlement_override import EntitlementOverride
from app.models.user import User
from app.repositories.platform_audit_log import PlatformAuditLogRepository

platform_entitlement_overrides_router = APIRouter(
    prefix="/entitlement-overrides", tags=["platform-entitlement-overrides"]
)

_VALID_LIMIT_KEYS = {
    "max_brands",
    "max_users",
    "max_brand_users",
    "max_brief_templates",
    "max_pending_agency_invites",
    "max_pending_brand_invites",
}


class EntitlementOverrideRead(BaseModel):
    id: uuid.UUID
    agency_id: uuid.UUID | None
    brand_id: uuid.UUID | None
    limit_key: str
    limit_value: int | None
    reason: str | None
    created_by_id: uuid.UUID

    model_config = {"from_attributes": True}


class EntitlementOverrideUpsertRequest(BaseModel):
    agency_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    limit_key: str
    limit_value: int | None = None
    reason: str | None = None

    @field_validator("limit_key")
    @classmethod
    def valid_limit_key(cls, v: str) -> str:
        if v not in _VALID_LIMIT_KEYS:
            raise ValueError(f"Geçersiz limit_key. Geçerli değerler: {sorted(_VALID_LIMIT_KEYS)}")
        return v


@platform_entitlement_overrides_router.get("", response_model=list[EntitlementOverrideRead])
async def list_overrides(
    agency_id: uuid.UUID | None = Query(default=None),
    brand_id: uuid.UUID | None = Query(default=None),
    _admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[EntitlementOverrideRead]:
    q = select(EntitlementOverride).where(EntitlementOverride.deleted_at.is_(None))
    if agency_id:
        q = q.where(EntitlementOverride.agency_id == agency_id)
    if brand_id:
        q = q.where(EntitlementOverride.brand_id == brand_id)
    rows = (await db.execute(q)).scalars().all()
    return [EntitlementOverrideRead.model_validate(r) for r in rows]


@platform_entitlement_overrides_router.put("", response_model=EntitlementOverrideRead)
async def upsert_override(
    body: EntitlementOverrideUpsertRequest,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> EntitlementOverrideRead:
    if (body.agency_id is None) == (body.brand_id is None):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Tam olarak agency_id veya brand_id belirtilmeli"
        )

    existing = (
        await db.execute(
            select(EntitlementOverride).where(
                EntitlementOverride.limit_key == body.limit_key,
                EntitlementOverride.deleted_at.is_(None),
                EntitlementOverride.agency_id == body.agency_id
                if body.brand_id is None
                else EntitlementOverride.brand_id == body.brand_id,
            )
        )
    ).scalar_one_or_none()

    old_value = existing.limit_value if existing else "(yok)"
    if existing is not None:
        existing.limit_value = body.limit_value
        existing.reason = body.reason
        existing.created_by_id = admin.id
        override = existing
    else:
        override = EntitlementOverride(
            agency_id=body.agency_id,
            brand_id=body.brand_id,
            limit_key=body.limit_key,
            limit_value=body.limit_value,
            reason=body.reason,
            created_by_id=admin.id,
        )
        db.add(override)

    await db.flush()
    await PlatformAuditLogRepository(db).create(
        admin_user_id=admin.id,
        action="entitlement_override.set",
        target_type="entitlement_override",
        target_id=override.id,
        target_tenant_type="agency" if body.agency_id else "brand",
        target_tenant_id=body.agency_id or body.brand_id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        meta={
            "limit_key": body.limit_key,
            "old_value": old_value,
            "new_value": body.limit_value,
            "reason": body.reason,
        },
    )
    await db.commit()
    await db.refresh(override)
    return EntitlementOverrideRead.model_validate(override)


@platform_entitlement_overrides_router.delete("/{override_id}")
async def delete_override(
    override_id: uuid.UUID,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    override = await db.get(EntitlementOverride, override_id)
    if override is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Override bulunamadı")

    old_value = override.limit_value
    override.soft_delete()
    await db.flush()
    await PlatformAuditLogRepository(db).create(
        admin_user_id=admin.id,
        action="entitlement_override.removed",
        target_type="entitlement_override",
        target_id=override.id,
        target_tenant_type="agency" if override.agency_id else "brand",
        target_tenant_id=override.agency_id or override.brand_id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        meta={"limit_key": override.limit_key, "old_value": old_value, "new_value": "(yok)"},
    )
    await db.commit()
    return {"message": "Override kaldırıldı"}

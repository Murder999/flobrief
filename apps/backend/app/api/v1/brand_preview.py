"""Brand-side Social Media Preview Center endpoints — read-only.

Mirrors ``brand_portal.py``'s deliverable section: brand users may only view
the same submitted/approved/revision_requested/rejected deliverables they can
already see in ``list_brand_deliverables``, never drafts. There is no write
endpoint here at all — a brand can never mutate preview config/slots,
structurally, not just via UI hiding.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.brand_portal_auth import BrandPortalContext, get_brand_portal_context
from app.db.session import get_db
from app.models.brief import Brief
from app.models.deliverable import Deliverable
from app.repositories.deliverable_preview import (
    DeliverablePreviewConfigRepository,
    DeliverablePreviewSlotRepository,
)
from app.schemas.deliverable_preview import PreviewConfigRead, PreviewSlotRead
from app.services.preview_validation_service import build_preview_config_read

brand_preview_router = APIRouter(prefix="/brand-portal", tags=["brand-portal-preview"])

_BRAND_VISIBLE_STATUSES = {"submitted", "approved", "revision_requested", "rejected"}


async def _require_brand_deliverable(
    brief_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    ctx: BrandPortalContext,
    db: AsyncSession,
) -> Deliverable:
    brief = (
        await db.execute(
            select(Brief).where(
                Brief.id == brief_id,
                Brief.brand_id == ctx.brand.id,
                Brief.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if brief is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brief bulunamadı")

    d = (
        await db.execute(
            select(Deliverable).where(
                Deliverable.id == deliverable_id,
                Deliverable.brief_id == brief_id,
                Deliverable.brand_id == ctx.brand.id,
                Deliverable.status.in_(_BRAND_VISIBLE_STATUSES),
                Deliverable.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if d is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deliverable bulunamadı")
    return d


@brand_preview_router.get(
    "/briefs/{brief_id}/deliverables/{deliverable_id}/preview-config",
    response_model=PreviewConfigRead,
)
async def get_brand_preview_config(
    brief_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> PreviewConfigRead:
    await _require_brand_deliverable(brief_id, deliverable_id, ctx, db)
    repo = DeliverablePreviewConfigRepository(db)
    config = await repo.get_by_deliverable(deliverable_id, ctx.brand.agency_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Önizleme yapılandırması bulunamadı")
    return await build_preview_config_read(config, db)


@brand_preview_router.get(
    "/briefs/{brief_id}/deliverables/{deliverable_id}/preview-slots",
    response_model=list[PreviewSlotRead],
)
async def list_brand_preview_slots(
    brief_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> list[PreviewSlotRead]:
    await _require_brand_deliverable(brief_id, deliverable_id, ctx, db)
    slot_repo = DeliverablePreviewSlotRepository(db)
    slots = await slot_repo.list_for_deliverable(deliverable_id)
    return [PreviewSlotRead.model_validate(s) for s in slots]

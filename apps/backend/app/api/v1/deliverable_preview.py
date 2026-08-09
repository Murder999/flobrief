"""Agency-side Social Media Preview Center endpoints.

Composition, not a parallel authority: reuses ``_require_brief``/
``_require_deliverable`` from ``app.api.v1.deliverables`` rather than
duplicating tenant-scoped lookup logic, and enforces the exact same
draft/revision_requested edit guard ``update_deliverable`` already applies —
that shared guard is the anti-carryover mechanism (a brand can only approve
while ``submitted``, so preview config/creative can never silently change on
an already-approved deliverable without first leaving that state through the
existing, unmodified revision-request flow).

No new ``Permission`` gate here, matching the existing convention that
``deliverables.py``/annotation endpoints only require an active workspace
membership (``get_workspace_context``) — adding a stricter gate than exists
for the deliverable itself would be an inconsistency.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deliverables import _require_brief, _require_deliverable
from app.core.auth_dependencies import WorkspaceContext, get_workspace_context
from app.db.session import get_db
from app.models.asset import AssetLink
from app.models.deliverable_preview import DeliverablePreviewConfig
from app.repositories.deliverable_preview import (
    DeliverablePreviewConfigRepository,
    DeliverablePreviewSlotRepository,
)
from app.schemas.deliverable_preview import (
    PreviewConfigRead,
    PreviewConfigUpsert,
    PreviewSlotRead,
    PreviewSlotsReorder,
)
from app.services.preview_validation_service import build_preview_config_read

preview_router = APIRouter(tags=["deliverable-preview"])

_EDITABLE_STATUSES = {"draft", "revision_requested"}


def _require_editable(status_value: str) -> None:
    if status_value not in _EDITABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Önizleme yalnızca taslak veya revizyon durumundaki deliverable "
                "için düzenlenebilir"
            ),
        )


async def _require_preview_config(
    deliverable_id: uuid.UUID,
    agency_id: uuid.UUID,
    db: AsyncSession,
) -> DeliverablePreviewConfig:
    repo = DeliverablePreviewConfigRepository(db)
    config = await repo.get_by_deliverable(deliverable_id, agency_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Önizleme yapılandırması bulunamadı")
    return config


async def _linked_asset_ids(deliverable_id: uuid.UUID, db: AsyncSession) -> set[uuid.UUID]:
    rows = await db.execute(
        select(AssetLink.asset_id).where(
            AssetLink.deliverable_id == deliverable_id,
            AssetLink.deleted_at.is_(None),
        )
    )
    return {row[0] for row in rows.all()}


@preview_router.get(
    "/briefs/{brief_id}/deliverables/{deliverable_id}/preview-config",
    response_model=PreviewConfigRead,
)
async def get_preview_config(
    brief_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> PreviewConfigRead:
    await _require_deliverable(brief_id, deliverable_id, workspace, db)
    config = await _require_preview_config(deliverable_id, workspace.agency.id, db)
    return await build_preview_config_read(config, db)


@preview_router.put(
    "/briefs/{brief_id}/deliverables/{deliverable_id}/preview-config",
    response_model=PreviewConfigRead,
)
async def upsert_preview_config(
    brief_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    data: PreviewConfigUpsert,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> PreviewConfigRead:
    brief = await _require_brief(brief_id, workspace, db)
    d = await _require_deliverable(brief_id, deliverable_id, workspace, db)
    _require_editable(d.status)

    if data.profile_photo_asset_id is not None or data.cover_asset_id is not None:
        linked = await _linked_asset_ids(deliverable_id, db)
        for field_name, asset_id in (
            ("profile_photo_asset_id", data.profile_photo_asset_id),
            ("cover_asset_id", data.cover_asset_id),
        ):
            if asset_id is not None and asset_id not in linked:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{field_name} bu deliverable'a bağlı bir asset olmalı",
                )

    repo = DeliverablePreviewConfigRepository(db)
    config = await repo.upsert(
        deliverable_id=deliverable_id,
        agency_id=workspace.agency.id,
        brand_id=d.brand_id,
        brief_id=brief.id,
        data=data.model_dump(),
        actor_user_id=workspace.user.id,
    )
    await db.commit()
    await db.refresh(config)
    return await build_preview_config_read(config, db)


@preview_router.get(
    "/briefs/{brief_id}/deliverables/{deliverable_id}/preview-slots",
    response_model=list[PreviewSlotRead],
)
async def list_preview_slots(
    brief_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> list[PreviewSlotRead]:
    await _require_deliverable(brief_id, deliverable_id, workspace, db)
    slot_repo = DeliverablePreviewSlotRepository(db)
    slots = await slot_repo.list_for_deliverable(deliverable_id)
    return [PreviewSlotRead.model_validate(s) for s in slots]


@preview_router.put(
    "/briefs/{brief_id}/deliverables/{deliverable_id}/preview-slots",
    response_model=list[PreviewSlotRead],
)
async def reorder_preview_slots(
    brief_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    data: PreviewSlotsReorder,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> list[PreviewSlotRead]:
    d = await _require_deliverable(brief_id, deliverable_id, workspace, db)
    _require_editable(d.status)

    linked = await _linked_asset_ids(deliverable_id, db)
    for item in data.slots:
        if item.asset_id not in linked:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Yalnızca bu deliverable'a bağlı asset'ler slayt olarak eklenebilir",
            )

    slot_repo = DeliverablePreviewSlotRepository(db)
    slots = await slot_repo.replace_all(
        deliverable_id,
        [
            {
                "asset_id": item.asset_id,
                "position": item.position,
                "is_cover": item.is_cover,
            }
            for item in data.slots
        ],
    )
    await db.commit()
    return [PreviewSlotRead.model_validate(s) for s in slots]

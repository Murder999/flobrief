"""Commercial-terms endpoints (plan §9): `GET/POST/PATCH
/finance/commercial-terms?brand_id=`. Every mutating endpoint writes an
`ActivityLogRepository` row; creating a new active term additionally logs a
`commercial_terms.superseded` entry whenever it closed out a prior one."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext, require_permission
from app.core.rbac import Permission
from app.db.session import get_db
from app.repositories.activity import ActivityLogRepository
from app.schemas.commercial_terms import (
    CommercialTermsCreate,
    CommercialTermsRead,
    CommercialTermsUpdate,
)
from app.services.commercial_terms_service import CommercialTermsService

commercial_terms_router = APIRouter(prefix="/finance", tags=["finance"])


@commercial_terms_router.get("/commercial-terms", response_model=list[CommercialTermsRead])
async def list_commercial_terms(
    brand_id: uuid.UUID = Query(...),
    workspace: WorkspaceContext = Depends(require_permission(Permission.COMMERCIAL_TERMS_VIEW)),
    db: AsyncSession = Depends(get_db),
) -> list[CommercialTermsRead]:
    items = await CommercialTermsService(db).list_for_brand(workspace.agency.id, brand_id)
    return [CommercialTermsRead.model_validate(i) for i in items]


@commercial_terms_router.post(
    "/commercial-terms", response_model=CommercialTermsRead, status_code=201
)
async def create_commercial_terms(
    data: CommercialTermsCreate,
    workspace: WorkspaceContext = Depends(require_permission(Permission.COMMERCIAL_TERMS_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> CommercialTermsRead:
    obj, superseded_id = await CommercialTermsService(db).create(
        workspace.agency.id, workspace.user.id, data
    )

    if superseded_id is not None:
        await ActivityLogRepository(db).create(
            action="commercial_terms.superseded",
            entity_type="commercial_terms",
            entity_id=superseded_id,
            agency_id=workspace.agency.id,
            brand_id=obj.brand_id,
            actor_user_id=workspace.user.id,
            meta={"superseded_by": str(obj.id)},
        )
    await ActivityLogRepository(db).create(
        action="commercial_terms.created",
        entity_type="commercial_terms",
        entity_id=obj.id,
        agency_id=workspace.agency.id,
        brand_id=obj.brand_id,
        actor_user_id=workspace.user.id,
        meta={
            "billing_model": obj.billing_model,
            "currency": obj.currency,
            "valid_from": obj.valid_from.isoformat(),
        },
    )
    await db.commit()
    return CommercialTermsRead.model_validate(obj)


@commercial_terms_router.patch("/commercial-terms/{terms_id}", response_model=CommercialTermsRead)
async def update_commercial_terms(
    terms_id: uuid.UUID,
    data: CommercialTermsUpdate,
    workspace: WorkspaceContext = Depends(require_permission(Permission.COMMERCIAL_TERMS_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> CommercialTermsRead:
    obj = await CommercialTermsService(db).update(
        workspace.agency.id, terms_id, workspace.user.id, data
    )

    await ActivityLogRepository(db).create(
        action="commercial_terms.updated",
        entity_type="commercial_terms",
        entity_id=obj.id,
        agency_id=workspace.agency.id,
        brand_id=obj.brand_id,
        actor_user_id=workspace.user.id,
        meta={"fields": list(data.model_dump(exclude_unset=True).keys())},
    )
    await db.commit()
    return CommercialTermsRead.model_validate(obj)

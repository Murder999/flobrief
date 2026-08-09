"""Profitability endpoints (plan §9, Phase 6): agency overview, brand
detail, and brief detail — all read-only, real-time aggregation, no
persisted "profitability" state. `PROFITABILITY_VIEW` gates access to the
endpoints themselves; `COST_RATE_VIEW` additionally gates whether cost/
margin fields within the response are populated or nulled
(`ProfitabilityService`'s `include_cost_data` parameter) — a caller with
`PROFITABILITY_VIEW` but not `COST_RATE_VIEW` (e.g. Brand Manager per plan
§8) still sees revenue/WIP/retainer figures, never cost or margin."""

from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext, require_permission
from app.core.exceptions import NotFoundError, ValidationError
from app.core.rbac import Permission
from app.db.session import get_db
from app.services.profitability_service import ProfitabilityService

profitability_router = APIRouter(prefix="/finance/profitability", tags=["finance-profitability"])


def _to_http(err: Exception) -> HTTPException:
    if isinstance(err, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err.message)
    if isinstance(err, ValidationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err.message)
    raise err


@profitability_router.get("/overview", response_model=dict)
async def get_overview(
    start: date | None = Query(None),
    end: date | None = Query(None),
    workspace: WorkspaceContext = Depends(require_permission(Permission.PROFITABILITY_VIEW)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await ProfitabilityService(db).get_agency_overview(
        workspace.agency.id,
        start=start,
        end=end,
        include_cost_data=workspace.has_permission(Permission.COST_RATE_VIEW),
    )
    return asdict(result)


@profitability_router.get("/brand/{brand_id}", response_model=dict)
async def get_brand(
    brand_id: uuid.UUID,
    start: date | None = Query(None),
    end: date | None = Query(None),
    as_of: date | None = Query(None),
    workspace: WorkspaceContext = Depends(require_permission(Permission.PROFITABILITY_VIEW)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        result = await ProfitabilityService(db).get_brand_profitability(
            workspace.agency.id,
            brand_id,
            start=start,
            end=end,
            include_cost_data=workspace.has_permission(Permission.COST_RATE_VIEW),
            as_of=as_of,
        )
    except (NotFoundError, ValidationError) as err:
        raise _to_http(err) from err
    return asdict(result)


@profitability_router.get("/brief/{brief_id}", response_model=dict)
async def get_brief(
    brief_id: uuid.UUID,
    as_of: date | None = Query(None),
    workspace: WorkspaceContext = Depends(require_permission(Permission.PROFITABILITY_VIEW)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        result = await ProfitabilityService(db).get_brief_profitability(
            workspace.agency.id,
            brief_id,
            include_cost_data=workspace.has_permission(Permission.COST_RATE_VIEW),
            as_of=as_of,
        )
    except (NotFoundError, ValidationError) as err:
        raise _to_http(err) from err
    return asdict(result)

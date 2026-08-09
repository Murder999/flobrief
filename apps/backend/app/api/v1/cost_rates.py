"""Member-cost-rate endpoints (plan §9): `GET/POST/PATCH
/finance/cost-rates?user_id=|role=` — Owner-only in practice (plan §8: no
other agency role gets `COST_RATE_VIEW`/`COST_RATE_MANAGE`). The service
layer re-checks the caller's role as defense-in-depth on top of this
router's `require_permission` gate, since cost rates must never leak to a
Designer/Developer/Social Media Manager/Brand Manager/brand-portal user
under any circumstance."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext, require_permission
from app.core.rbac import Permission
from app.db.session import get_db
from app.repositories.activity import ActivityLogRepository
from app.schemas.member_cost_rate import (
    MemberCostRateCreate,
    MemberCostRateRead,
    MemberCostRateUpdate,
)
from app.services.member_cost_rate_service import MemberCostRateService

cost_rates_router = APIRouter(prefix="/finance", tags=["finance"])


@cost_rates_router.get("/cost-rates", response_model=list[MemberCostRateRead])
async def list_cost_rates(
    user_id: uuid.UUID | None = Query(default=None),
    role: str | None = Query(default=None),
    workspace: WorkspaceContext = Depends(require_permission(Permission.COST_RATE_VIEW)),
    db: AsyncSession = Depends(get_db),
) -> list[MemberCostRateRead]:
    if (user_id is None) == (role is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tam olarak biri belirtilmeli: user_id veya role",
        )
    svc = MemberCostRateService(db)
    if user_id is not None:
        items = await svc.list_for_user(workspace.agency.id, user_id, workspace.member.role)
    else:
        items = await svc.list_for_role(workspace.agency.id, role, workspace.member.role)  # type: ignore[arg-type]
    return [MemberCostRateRead.model_validate(i) for i in items]


@cost_rates_router.post("/cost-rates", response_model=MemberCostRateRead, status_code=201)
async def create_cost_rate(
    data: MemberCostRateCreate,
    workspace: WorkspaceContext = Depends(require_permission(Permission.COST_RATE_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> MemberCostRateRead:
    obj, superseded_id = await MemberCostRateService(db).create(
        workspace.agency.id, workspace.user.id, workspace.member.role, data
    )

    if superseded_id is not None:
        await ActivityLogRepository(db).create(
            action="member_cost_rate.superseded",
            entity_type="member_cost_rate",
            entity_id=superseded_id,
            agency_id=workspace.agency.id,
            actor_user_id=workspace.user.id,
            meta={"superseded_by": str(obj.id)},
        )
    await ActivityLogRepository(db).create(
        action="member_cost_rate.created",
        entity_type="member_cost_rate",
        entity_id=obj.id,
        agency_id=workspace.agency.id,
        actor_user_id=workspace.user.id,
        meta={
            "target_user_id": str(obj.user_id) if obj.user_id else None,
            "target_role": obj.role,
        },
    )
    await db.commit()
    return MemberCostRateRead.model_validate(obj)


@cost_rates_router.patch("/cost-rates/{rate_id}", response_model=MemberCostRateRead)
async def update_cost_rate(
    rate_id: uuid.UUID,
    data: MemberCostRateUpdate,
    workspace: WorkspaceContext = Depends(require_permission(Permission.COST_RATE_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> MemberCostRateRead:
    obj = await MemberCostRateService(db).update(
        workspace.agency.id, rate_id, workspace.member.role, data
    )

    await ActivityLogRepository(db).create(
        action="member_cost_rate.updated",
        entity_type="member_cost_rate",
        entity_id=obj.id,
        agency_id=workspace.agency.id,
        actor_user_id=workspace.user.id,
        meta={"fields": list(data.model_dump(exclude_unset=True).keys())},
    )
    await db.commit()
    return MemberCostRateRead.model_validate(obj)

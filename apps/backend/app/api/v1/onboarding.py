from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext, get_workspace_context
from app.db.session import get_db
from app.schemas.onboarding import OnboardingProgressRead, OnboardingStepRead
from app.services.onboarding_service import (
    OnboardingService,
    ProgressView,
    default_onboarding_type_for_agency_role,
)

onboarding_router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _to_read(view: ProgressView) -> OnboardingProgressRead:
    return OnboardingProgressRead(
        id=view.id,
        onboarding_type=view.onboarding_type,
        current_step=view.current_step,
        started_at=view.started_at,
        completed_at=view.completed_at,
        dismissed_at=view.dismissed_at,
        version=view.version,
        percent_complete=view.percent_complete,
        steps=[
            OnboardingStepRead(
                key=s.key,
                completed=s.completed,
                kind=s.kind,
                skipped=s.skipped,
                first_seen_at=s.first_seen_at,
                last_seen_at=s.last_seen_at,
            )
            for s in view.steps
        ],
    )


@onboarding_router.get("/progress", response_model=OnboardingProgressRead)
async def get_onboarding_progress(
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> OnboardingProgressRead:
    """Always scoped to the authenticated user's own membership — the
    onboarding_type is derived server-side from their real role, never
    accepted from the client, so one user can never read/drive another's
    onboarding state (§L onboarding state IDOR)."""
    onboarding_type = default_onboarding_type_for_agency_role(workspace.member.role)
    service = OnboardingService(db)
    view = await service.build_progress_view(
        user_id=workspace.user.id,
        agency_id=workspace.agency.id,
        brand_id=None,
        onboarding_type=onboarding_type,
    )
    await db.commit()
    return _to_read(view)


@onboarding_router.post("/progress/dismiss", response_model=OnboardingProgressRead)
async def dismiss_onboarding(
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> OnboardingProgressRead:
    onboarding_type = default_onboarding_type_for_agency_role(workspace.member.role)
    service = OnboardingService(db)
    progress = await service.get_or_create_progress(
        user_id=workspace.user.id, agency_id=workspace.agency.id, onboarding_type=onboarding_type
    )
    await service.dismiss(progress=progress)
    view = await service.build_progress_view(
        user_id=workspace.user.id,
        agency_id=workspace.agency.id,
        brand_id=None,
        onboarding_type=onboarding_type,
    )
    await db.commit()
    return _to_read(view)


@onboarding_router.post("/progress/resume", response_model=OnboardingProgressRead)
async def resume_onboarding(
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> OnboardingProgressRead:
    onboarding_type = default_onboarding_type_for_agency_role(workspace.member.role)
    service = OnboardingService(db)
    progress = await service.get_or_create_progress(
        user_id=workspace.user.id, agency_id=workspace.agency.id, onboarding_type=onboarding_type
    )
    await service.resume(progress=progress)
    view = await service.build_progress_view(
        user_id=workspace.user.id,
        agency_id=workspace.agency.id,
        brand_id=None,
        onboarding_type=onboarding_type,
    )
    await db.commit()
    return _to_read(view)


@onboarding_router.post("/progress/step/{step_key}/seen", response_model=OnboardingProgressRead)
async def mark_onboarding_step_seen(
    step_key: str,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> OnboardingProgressRead:
    onboarding_type = default_onboarding_type_for_agency_role(workspace.member.role)
    service = OnboardingService(db)
    progress = await service.get_or_create_progress(
        user_id=workspace.user.id, agency_id=workspace.agency.id, onboarding_type=onboarding_type
    )
    view = await service.build_progress_view(
        user_id=workspace.user.id,
        agency_id=workspace.agency.id,
        brand_id=None,
        onboarding_type=onboarding_type,
    )
    if step_key not in {s.key for s in view.steps}:
        raise HTTPException(status_code=404, detail="Bilinmeyen onboarding adımı")
    await service.mark_step_seen(progress=progress, step_key=step_key)
    view = await service.build_progress_view(
        user_id=workspace.user.id,
        agency_id=workspace.agency.id,
        brand_id=None,
        onboarding_type=onboarding_type,
    )
    await db.commit()
    return _to_read(view)


@onboarding_router.post("/progress/step/{step_key}/skip", response_model=OnboardingProgressRead)
async def skip_onboarding_step(
    step_key: str,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> OnboardingProgressRead:
    onboarding_type = default_onboarding_type_for_agency_role(workspace.member.role)
    service = OnboardingService(db)
    progress = await service.get_or_create_progress(
        user_id=workspace.user.id, agency_id=workspace.agency.id, onboarding_type=onboarding_type
    )
    view = await service.build_progress_view(
        user_id=workspace.user.id,
        agency_id=workspace.agency.id,
        brand_id=None,
        onboarding_type=onboarding_type,
    )
    if step_key not in {s.key for s in view.steps}:
        raise HTTPException(status_code=404, detail="Bilinmeyen onboarding adımı")
    await service.skip_step(progress=progress, step_key=step_key)
    view = await service.build_progress_view(
        user_id=workspace.user.id,
        agency_id=workspace.agency.id,
        brand_id=None,
        onboarding_type=onboarding_type,
    )
    await db.commit()
    return _to_read(view)

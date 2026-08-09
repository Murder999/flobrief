from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext, get_workspace_context
from app.core.rate_limiter import rate_limit_mention_candidates
from app.db.session import get_db
from app.schemas.mention import MentionCandidateListResponse
from app.services.mention_service import MentionService

mention_router = APIRouter(prefix="/mentions", tags=["mentions"])

_VALID_SOURCE_TYPES = {"comment", "annotation", "annotation_reply"}


@mention_router.get("/candidates", response_model=MentionCandidateListResponse)
async def list_mention_candidates(
    source_type: Annotated[str, Query()],
    source_id: Annotated[uuid.UUID | None, Query()] = None,
    query: Annotated[str | None, Query(max_length=100)] = None,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> MentionCandidateListResponse:
    """Agency-side mentionable people for a comment/annotation/reply composer.

    ``source_id`` is accepted for API symmetry with the brand-portal variant
    but unused agency-side today — agency candidates are always "everyone on
    my own agency team except viewers", regardless of which brief/deliverable
    the composer is open on.
    """
    del source_id  # symmetry only, see docstring
    if source_type not in _VALID_SOURCE_TYPES:
        return MentionCandidateListResponse(items=[])

    await rate_limit_mention_candidates(str(workspace.user.id))

    service = MentionService(db)
    candidates = await service.get_agency_candidates(
        agency_id=workspace.agency.id,
        query=query,
        exclude_user_id=workspace.user.id,
    )
    return MentionCandidateListResponse(items=candidates)

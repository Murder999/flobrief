from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_204_NO_CONTENT

from app.core.auth_dependencies import WorkspaceContext, get_workspace_context
from app.db.session import get_db
from app.schemas.brief_template import (
    FieldCreate,
    FieldRead,
    FieldUpdate,
    IndustryRead,
    ReorderFieldsRequest,
    ReorderSectionsRequest,
    SectionCreate,
    SectionRead,
    SectionUpdate,
    TemplateCreate,
    TemplateDetail,
    TemplateRead,
    TemplateUpdate,
)
from app.services.brief_template_service import (
    BriefTemplateIndustryService,
    BriefTemplateService,
)

template_router = APIRouter(prefix="/templates", tags=["templates"])
industry_router = APIRouter(prefix="/industries", tags=["industries"])


# ── Industries ────────────────────────────────────────────────────────────────


@industry_router.get("", response_model=list[IndustryRead])
async def list_industries(
    db: AsyncSession = Depends(get_db),
) -> list[IndustryRead]:
    svc = BriefTemplateIndustryService(db)
    return await svc.list_industries()


# ── Templates ─────────────────────────────────────────────────────────────────


@template_router.get("", response_model=list[TemplateRead])
async def list_templates(
    industry: str | None = None,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> list[TemplateRead]:
    svc = BriefTemplateService(db, workspace)
    return await svc.list_templates(industry=industry)


@template_router.post("", response_model=TemplateRead, status_code=201)
async def create_template(
    data: TemplateCreate,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> TemplateRead:
    svc = BriefTemplateService(db, workspace)
    return await svc.create_template(data)


@template_router.get("/{template_id}", response_model=TemplateDetail)
async def get_template(
    template_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> TemplateDetail:
    svc = BriefTemplateService(db, workspace)
    return await svc.get_template(template_id)


@template_router.patch("/{template_id}", response_model=TemplateRead)
async def update_template(
    template_id: uuid.UUID,
    data: TemplateUpdate,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> TemplateRead:
    svc = BriefTemplateService(db, workspace)
    return await svc.update_template(template_id, data)


@template_router.post("/{template_id}/archive", response_model=TemplateRead)
async def archive_template(
    template_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> TemplateRead:
    svc = BriefTemplateService(db, workspace)
    return await svc.archive_template(template_id)


@template_router.post("/{template_id}/duplicate", response_model=TemplateRead, status_code=201)
async def duplicate_template(
    template_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> TemplateRead:
    svc = BriefTemplateService(db, workspace)
    return await svc.duplicate_template(template_id)


# ── Sections ──────────────────────────────────────────────────────────────────


@template_router.post("/{template_id}/sections", response_model=SectionRead, status_code=201)
async def add_section(
    template_id: uuid.UUID,
    data: SectionCreate,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> SectionRead:
    svc = BriefTemplateService(db, workspace)
    return await svc.add_section(template_id, data)


@template_router.patch("/{template_id}/sections/{section_id}", response_model=SectionRead)
async def update_section(
    template_id: uuid.UUID,
    section_id: uuid.UUID,
    data: SectionUpdate,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> SectionRead:
    svc = BriefTemplateService(db, workspace)
    return await svc.update_section(template_id, section_id, data)


@template_router.delete("/{template_id}/sections/{section_id}", response_model=None)
async def delete_section(
    template_id: uuid.UUID,
    section_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    svc = BriefTemplateService(db, workspace)
    await svc.delete_section(template_id, section_id)
    return Response(status_code=HTTP_204_NO_CONTENT)


@template_router.post(
    "/{template_id}/sections/reorder",
    response_model=list[SectionRead],
)
async def reorder_sections(
    template_id: uuid.UUID,
    data: ReorderSectionsRequest,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> list[SectionRead]:
    svc = BriefTemplateService(db, workspace)
    return await svc.reorder_sections(template_id, data)


# ── Fields ────────────────────────────────────────────────────────────────────


@template_router.post(
    "/{template_id}/sections/{section_id}/fields",
    response_model=FieldRead,
    status_code=201,
)
async def add_field(
    template_id: uuid.UUID,
    section_id: uuid.UUID,
    data: FieldCreate,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> FieldRead:
    svc = BriefTemplateService(db, workspace)
    return await svc.add_field(template_id, section_id, data)


@template_router.patch(
    "/{template_id}/sections/{section_id}/fields/{field_id}",
    response_model=FieldRead,
)
async def update_field(
    template_id: uuid.UUID,
    section_id: uuid.UUID,
    field_id: uuid.UUID,
    data: FieldUpdate,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> FieldRead:
    svc = BriefTemplateService(db, workspace)
    return await svc.update_field(template_id, section_id, field_id, data)


@template_router.delete(
    "/{template_id}/sections/{section_id}/fields/{field_id}",
    response_model=None,
)
async def delete_field(
    template_id: uuid.UUID,
    section_id: uuid.UUID,
    field_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    svc = BriefTemplateService(db, workspace)
    await svc.delete_field(template_id, section_id, field_id)
    return Response(status_code=HTTP_204_NO_CONTENT)


@template_router.post(
    "/{template_id}/sections/{section_id}/fields/reorder",
    response_model=list[FieldRead],
)
async def reorder_fields(
    template_id: uuid.UUID,
    section_id: uuid.UUID,
    data: ReorderFieldsRequest,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> list[FieldRead]:
    svc = BriefTemplateService(db, workspace)
    return await svc.reorder_fields(template_id, section_id, data)

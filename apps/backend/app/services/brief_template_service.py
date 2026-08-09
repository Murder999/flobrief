from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext
from app.core.rbac import Permission
from app.models.enums import FieldType
from app.repositories.brief_template import (
    BriefTemplateFieldRepository,
    BriefTemplateIndustryRepository,
    BriefTemplateRepository,
    BriefTemplateSectionRepository,
)
from app.schemas.brief_template import (
    FieldCreate,
    FieldRead,
    FieldUpdate,
    IndustryRead,
    ReorderFieldsRequest,
    ReorderSectionsRequest,
    SectionCreate,
    SectionDetail,
    SectionRead,
    SectionUpdate,
    TemplateCreate,
    TemplateDetail,
    TemplateRead,
    TemplateUpdate,
)
from app.services.entitlement_service import EntitlementService

FIELDS_REQUIRING_OPTIONS = {FieldType.SELECT.value, FieldType.MULTI_SELECT.value}


def _require(workspace: WorkspaceContext, perm: Permission) -> None:
    if not workspace.has_permission(perm):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )


class BriefTemplateService:
    def __init__(self, db: AsyncSession, workspace: WorkspaceContext) -> None:
        self.db = db
        self.workspace = workspace
        self.repo = BriefTemplateRepository(db)
        self.section_repo = BriefTemplateSectionRepository(db)
        self.field_repo = BriefTemplateFieldRepository(db)

    # ── Template CRUD ────────────────────────────────────────────────────────

    async def list_templates(self, *, industry: str | None = None) -> list[TemplateRead]:
        _require(self.workspace, Permission.TEMPLATE_VIEW)
        rows = await self.repo.list_for_agency(
            self.workspace.agency.id,
            include_system=True,
            industry=industry,
        )
        return [TemplateRead.model_validate(r) for r in rows]

    async def get_template(self, template_id: uuid.UUID) -> TemplateDetail:
        _require(self.workspace, Permission.TEMPLATE_VIEW)
        template = await self.repo.get(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        self._assert_template_accessible(template)

        sections = await self.section_repo.list_for_template(template_id)
        section_details: list[SectionDetail] = []
        for section in sections:
            fields = await self.field_repo.list_for_section(section.id)
            section_details.append(
                SectionDetail(
                    **SectionRead.model_validate(section).model_dump(),
                    fields=[FieldRead.model_validate(f) for f in fields],
                )
            )
        detail = TemplateDetail(
            **TemplateRead.model_validate(template).model_dump(),
            sections=section_details,
        )
        return detail

    async def create_template(self, data: TemplateCreate) -> TemplateRead:
        _require(self.workspace, Permission.TEMPLATE_CREATE)
        await EntitlementService(self.db).check_template_limit(self.workspace.agency.id)
        template = await self.repo.create(
            agency_id=self.workspace.agency.id,
            name=data.name,
            description=data.description,
            industry=data.industry,
            is_system_template=False,
            is_active=True,
            created_by_id=self.workspace.user.id,
        )
        await self.db.commit()
        await self.db.refresh(template)
        return TemplateRead.model_validate(template)

    async def update_template(self, template_id: uuid.UUID, data: TemplateUpdate) -> TemplateRead:
        _require(self.workspace, Permission.TEMPLATE_UPDATE)
        template = await self.repo.get(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        self._assert_template_owned_by_agency(template)

        updates = data.model_dump(exclude_unset=True)
        template = await self.repo.update(template, **updates)
        await self.db.commit()
        await self.db.refresh(template)
        return TemplateRead.model_validate(template)

    async def archive_template(self, template_id: uuid.UUID) -> TemplateRead:
        _require(self.workspace, Permission.TEMPLATE_ARCHIVE)
        template = await self.repo.get(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        self._assert_template_owned_by_agency(template)

        template = await self.repo.archive(template)
        await self.db.commit()
        await self.db.refresh(template)
        return TemplateRead.model_validate(template)

    async def duplicate_template(self, template_id: uuid.UUID) -> TemplateRead:
        _require(self.workspace, Permission.TEMPLATE_CREATE)
        source = await self.repo.get(template_id)
        if not source:
            raise HTTPException(status_code=404, detail="Template not found")
        self._assert_template_accessible(source)

        new_template = await self.repo.create(
            agency_id=self.workspace.agency.id,
            name=f"{source.name} (Kopya)",
            description=source.description,
            industry=source.industry,
            is_system_template=False,
            is_active=True,
            created_by_id=self.workspace.user.id,
        )

        sections = await self.section_repo.list_for_template(template_id)
        for section in sections:
            new_section = await self.section_repo.create(
                template_id=new_template.id,
                title=section.title,
                description=section.description,
                sort_order=section.sort_order,
            )
            fields = await self.field_repo.list_for_section(section.id)
            for field in fields:
                await self.field_repo.create(
                    section_id=new_section.id,
                    field_key=field.field_key,
                    label=field.label,
                    help_text=field.help_text,
                    field_type=field.field_type,
                    is_required=field.is_required,
                    options=field.options,
                    validation_rules=field.validation_rules,
                    placeholder=field.placeholder,
                    sort_order=field.sort_order,
                )

        await self.db.commit()
        await self.db.refresh(new_template)
        return TemplateRead.model_validate(new_template)

    # ── Section CRUD ──────────────────────────────────────────────────────────

    async def add_section(self, template_id: uuid.UUID, data: SectionCreate) -> SectionRead:
        _require(self.workspace, Permission.TEMPLATE_UPDATE)
        template = await self.repo.get(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        self._assert_template_owned_by_agency(template)

        section = await self.section_repo.create(
            template_id=template_id,
            title=data.title,
            description=data.description,
            sort_order=data.sort_order,
        )
        await self.db.commit()
        await self.db.refresh(section)
        return SectionRead.model_validate(section)

    async def update_section(
        self, template_id: uuid.UUID, section_id: uuid.UUID, data: SectionUpdate
    ) -> SectionRead:
        _require(self.workspace, Permission.TEMPLATE_UPDATE)
        section = await self.section_repo.get(section_id)
        if not section or section.template_id != template_id:
            raise HTTPException(status_code=404, detail="Section not found")
        template = await self.repo.get(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        self._assert_template_owned_by_agency(template)

        updates = data.model_dump(exclude_unset=True)
        section = await self.section_repo.update(section, **updates)
        await self.db.commit()
        await self.db.refresh(section)
        return SectionRead.model_validate(section)

    async def delete_section(self, template_id: uuid.UUID, section_id: uuid.UUID) -> None:
        _require(self.workspace, Permission.TEMPLATE_UPDATE)
        section = await self.section_repo.get(section_id)
        if not section or section.template_id != template_id:
            raise HTTPException(status_code=404, detail="Section not found")
        template = await self.repo.get(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        self._assert_template_owned_by_agency(template)

        await self.section_repo.soft_delete(section)
        await self.db.commit()

    async def reorder_sections(
        self, template_id: uuid.UUID, data: ReorderSectionsRequest
    ) -> list[SectionRead]:
        _require(self.workspace, Permission.TEMPLATE_UPDATE)
        template = await self.repo.get(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        self._assert_template_owned_by_agency(template)

        await self.section_repo.bulk_reorder(template_id, data.ordered_ids)
        await self.db.commit()
        rows = await self.section_repo.list_for_template(template_id)
        return [SectionRead.model_validate(r) for r in rows]

    # ── Field CRUD ────────────────────────────────────────────────────────────

    async def add_field(
        self, template_id: uuid.UUID, section_id: uuid.UUID, data: FieldCreate
    ) -> FieldRead:
        _require(self.workspace, Permission.TEMPLATE_UPDATE)
        section = await self.section_repo.get(section_id)
        if not section or section.template_id != template_id:
            raise HTTPException(status_code=404, detail="Section not found")
        template = await self.repo.get(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        self._assert_template_owned_by_agency(template)

        if await self.repo.field_key_exists_in_template(template_id, data.field_key):
            raise HTTPException(
                status_code=400,
                detail=f"field_key '{data.field_key}' already exists in this template",
            )

        if data.field_type in FIELDS_REQUIRING_OPTIONS and not data.options:
            raise HTTPException(
                status_code=400,
                detail=f"options required for field_type '{data.field_type}'",
            )

        field = await self.field_repo.create(
            section_id=section_id,
            field_key=data.field_key,
            label=data.label,
            help_text=data.help_text,
            field_type=data.field_type,
            is_required=data.is_required,
            options=data.options,
            validation_rules=data.validation_rules,
            placeholder=data.placeholder,
            sort_order=data.sort_order,
        )
        await self.db.commit()
        await self.db.refresh(field)
        return FieldRead.model_validate(field)

    async def update_field(
        self,
        template_id: uuid.UUID,
        section_id: uuid.UUID,
        field_id: uuid.UUID,
        data: FieldUpdate,
    ) -> FieldRead:
        _require(self.workspace, Permission.TEMPLATE_UPDATE)
        field = await self.field_repo.get(field_id)
        if not field or field.section_id != section_id:
            raise HTTPException(status_code=404, detail="Field not found")
        section = await self.section_repo.get(section_id)
        if not section or section.template_id != template_id:
            raise HTTPException(status_code=404, detail="Section not found")
        template = await self.repo.get(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        self._assert_template_owned_by_agency(template)

        effective_type = data.field_type or field.field_type
        effective_options = data.options if "options" in data.model_fields_set else field.options
        if effective_type in FIELDS_REQUIRING_OPTIONS and not effective_options:
            raise HTTPException(
                status_code=400,
                detail=f"options required for field_type '{effective_type}'",
            )

        updates = data.model_dump(exclude_unset=True)
        field = await self.field_repo.update(field, **updates)
        await self.db.commit()
        await self.db.refresh(field)
        return FieldRead.model_validate(field)

    async def delete_field(
        self, template_id: uuid.UUID, section_id: uuid.UUID, field_id: uuid.UUID
    ) -> None:
        _require(self.workspace, Permission.TEMPLATE_UPDATE)
        field = await self.field_repo.get(field_id)
        if not field or field.section_id != section_id:
            raise HTTPException(status_code=404, detail="Field not found")
        section = await self.section_repo.get(section_id)
        if not section or section.template_id != template_id:
            raise HTTPException(status_code=404, detail="Section not found")
        template = await self.repo.get(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        self._assert_template_owned_by_agency(template)

        await self.field_repo.soft_delete(field)
        await self.db.commit()

    async def reorder_fields(
        self,
        template_id: uuid.UUID,
        section_id: uuid.UUID,
        data: ReorderFieldsRequest,
    ) -> list[FieldRead]:
        _require(self.workspace, Permission.TEMPLATE_UPDATE)
        section = await self.section_repo.get(section_id)
        if not section or section.template_id != template_id:
            raise HTTPException(status_code=404, detail="Section not found")
        template = await self.repo.get(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        self._assert_template_owned_by_agency(template)

        await self.field_repo.bulk_reorder(section_id, data.ordered_ids)
        await self.db.commit()
        rows = await self.field_repo.list_for_section(section_id)
        return [FieldRead.model_validate(r) for r in rows]

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _assert_template_accessible(self, template: object) -> None:
        is_system = getattr(template, "is_system_template", False)
        tmpl_agency_id = getattr(template, "agency_id", None)
        if not is_system and tmpl_agency_id != self.workspace.agency.id:
            raise HTTPException(status_code=404, detail="Template not found")

    def _assert_template_owned_by_agency(self, template: object) -> None:
        is_system = getattr(template, "is_system_template", False)
        tmpl_agency_id = getattr(template, "agency_id", None)
        if is_system or tmpl_agency_id != self.workspace.agency.id:
            raise HTTPException(
                status_code=403,
                detail="System templates cannot be modified",
            )


class BriefTemplateIndustryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = BriefTemplateIndustryRepository(db)

    async def list_industries(self) -> list[IndustryRead]:
        rows = await self.repo.list_active()
        return [IndustryRead.model_validate(r) for r in rows]

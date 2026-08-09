from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brief_template import (
    BriefTemplate,
    BriefTemplateField,
    BriefTemplateIndustry,
    BriefTemplateSection,
)


class BriefTemplateRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, **kwargs: object) -> BriefTemplate:
        obj = BriefTemplate(**kwargs)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def get(self, template_id: uuid.UUID) -> BriefTemplate | None:
        result = await self.db.execute(
            select(BriefTemplate).where(
                BriefTemplate.id == template_id,
                BriefTemplate.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_agency(
        self,
        agency_id: uuid.UUID,
        *,
        include_system: bool = True,
        industry: str | None = None,
        active_only: bool = True,
    ) -> Sequence[BriefTemplate]:
        conditions = [BriefTemplate.deleted_at.is_(None)]
        if include_system:
            conditions.append(
                (BriefTemplate.agency_id == agency_id)
                | (BriefTemplate.is_system_template.is_(True))
            )
        else:
            conditions.append(BriefTemplate.agency_id == agency_id)
        if active_only:
            conditions.append(BriefTemplate.is_active.is_(True))
        if industry:
            conditions.append(BriefTemplate.industry == industry)
        result = await self.db.execute(
            select(BriefTemplate).where(*conditions).order_by(BriefTemplate.name)
        )
        return result.scalars().all()

    async def list_system_templates(
        self, *, industry: str | None = None
    ) -> Sequence[BriefTemplate]:
        conditions = [
            BriefTemplate.is_system_template.is_(True),
            BriefTemplate.deleted_at.is_(None),
            BriefTemplate.is_active.is_(True),
        ]
        if industry:
            conditions.append(BriefTemplate.industry == industry)
        result = await self.db.execute(
            select(BriefTemplate).where(*conditions).order_by(BriefTemplate.name)
        )
        return result.scalars().all()

    async def update(self, template: BriefTemplate, **kwargs: object) -> BriefTemplate:
        for key, value in kwargs.items():
            setattr(template, key, value)
        await self.db.flush()
        await self.db.refresh(template)
        return template

    async def soft_delete(self, template: BriefTemplate) -> None:
        from datetime import datetime

        template.deleted_at = datetime.now(UTC)
        await self.db.flush()

    async def archive(self, template: BriefTemplate) -> BriefTemplate:
        template.is_active = False
        await self.db.flush()
        await self.db.refresh(template)
        return template

    async def field_key_exists_in_template(
        self, template_id: uuid.UUID, field_key: str, exclude_field_id: uuid.UUID | None = None
    ) -> bool:
        conditions = [
            BriefTemplateSection.template_id == template_id,
            BriefTemplateField.field_key == field_key,
            BriefTemplateField.deleted_at.is_(None),
            BriefTemplateSection.deleted_at.is_(None),
        ]
        if exclude_field_id:
            conditions.append(BriefTemplateField.id != exclude_field_id)
        result = await self.db.execute(
            select(BriefTemplateField.id)
            .join(BriefTemplateSection, BriefTemplateField.section_id == BriefTemplateSection.id)
            .where(*conditions)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None


class BriefTemplateSectionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, **kwargs: object) -> BriefTemplateSection:
        obj = BriefTemplateSection(**kwargs)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def get(self, section_id: uuid.UUID) -> BriefTemplateSection | None:
        result = await self.db.execute(
            select(BriefTemplateSection).where(
                BriefTemplateSection.id == section_id,
                BriefTemplateSection.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_template(self, template_id: uuid.UUID) -> Sequence[BriefTemplateSection]:
        result = await self.db.execute(
            select(BriefTemplateSection)
            .where(
                BriefTemplateSection.template_id == template_id,
                BriefTemplateSection.deleted_at.is_(None),
            )
            .order_by(BriefTemplateSection.sort_order, BriefTemplateSection.created_at)
        )
        return result.scalars().all()

    async def update(self, section: BriefTemplateSection, **kwargs: object) -> BriefTemplateSection:
        for key, value in kwargs.items():
            setattr(section, key, value)
        await self.db.flush()
        await self.db.refresh(section)
        return section

    async def soft_delete(self, section: BriefTemplateSection) -> None:
        from datetime import datetime

        section.deleted_at = datetime.now(UTC)
        await self.db.flush()

    async def bulk_reorder(self, template_id: uuid.UUID, ordered_ids: list[uuid.UUID]) -> None:
        for i, section_id in enumerate(ordered_ids):
            await self.db.execute(
                update(BriefTemplateSection)
                .where(
                    BriefTemplateSection.id == section_id,
                    BriefTemplateSection.template_id == template_id,
                    BriefTemplateSection.deleted_at.is_(None),
                )
                .values(sort_order=i)
            )
        await self.db.flush()


class BriefTemplateFieldRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, **kwargs: object) -> BriefTemplateField:
        obj = BriefTemplateField(**kwargs)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def get(self, field_id: uuid.UUID) -> BriefTemplateField | None:
        result = await self.db.execute(
            select(BriefTemplateField).where(
                BriefTemplateField.id == field_id,
                BriefTemplateField.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_section(self, section_id: uuid.UUID) -> Sequence[BriefTemplateField]:
        result = await self.db.execute(
            select(BriefTemplateField)
            .where(
                BriefTemplateField.section_id == section_id,
                BriefTemplateField.deleted_at.is_(None),
            )
            .order_by(BriefTemplateField.sort_order, BriefTemplateField.created_at)
        )
        return result.scalars().all()

    async def list_for_template(self, template_id: uuid.UUID) -> Sequence[BriefTemplateField]:
        result = await self.db.execute(
            select(BriefTemplateField)
            .join(BriefTemplateSection, BriefTemplateField.section_id == BriefTemplateSection.id)
            .where(
                BriefTemplateSection.template_id == template_id,
                BriefTemplateField.deleted_at.is_(None),
                BriefTemplateSection.deleted_at.is_(None),
            )
            .order_by(BriefTemplateField.sort_order)
        )
        return result.scalars().all()

    async def update(self, field: BriefTemplateField, **kwargs: object) -> BriefTemplateField:
        for key, value in kwargs.items():
            setattr(field, key, value)
        await self.db.flush()
        await self.db.refresh(field)
        return field

    async def soft_delete(self, field: BriefTemplateField) -> None:
        from datetime import datetime

        field.deleted_at = datetime.now(UTC)
        await self.db.flush()

    async def bulk_reorder(self, section_id: uuid.UUID, ordered_ids: list[uuid.UUID]) -> None:
        for i, field_id in enumerate(ordered_ids):
            await self.db.execute(
                update(BriefTemplateField)
                .where(
                    BriefTemplateField.id == field_id,
                    BriefTemplateField.section_id == section_id,
                    BriefTemplateField.deleted_at.is_(None),
                )
                .values(sort_order=i)
            )
        await self.db.flush()


class BriefTemplateIndustryRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_active(self) -> Sequence[BriefTemplateIndustry]:
        result = await self.db.execute(
            select(BriefTemplateIndustry)
            .where(
                BriefTemplateIndustry.is_active.is_(True),
                BriefTemplateIndustry.deleted_at.is_(None),
            )
            .order_by(BriefTemplateIndustry.name)
        )
        return result.scalars().all()

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brief import Brief, BriefAssignee, BriefFieldValue


class BriefRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, brief_id: uuid.UUID, agency_id: uuid.UUID) -> Brief | None:
        result = await self.db.execute(
            select(Brief).where(
                and_(Brief.id == brief_id, Brief.agency_id == agency_id, Brief.deleted_at.is_(None))
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        agency_id: uuid.UUID,
        *,
        brand_id: uuid.UUID | None = None,
        status: str | None = None,
        priority: str | None = None,
        assignee_id: uuid.UUID | None = None,
        deadline_before: str | None = None,
        search: str | None = None,
        source: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Brief], int]:
        base_q = select(Brief).where(and_(Brief.agency_id == agency_id, Brief.deleted_at.is_(None)))
        if brand_id:
            base_q = base_q.where(Brief.brand_id == brand_id)
        if status:
            base_q = base_q.where(Brief.status == status)
        if priority:
            base_q = base_q.where(Brief.priority == priority)
        if deadline_before:
            base_q = base_q.where(Brief.deadline <= deadline_before)
        if search:
            term = f"%{search}%"
            base_q = base_q.where(Brief.title.ilike(term))
        if source:
            base_q = base_q.where(Brief.source == source)
        if assignee_id:
            sub = select(BriefAssignee.brief_id).where(BriefAssignee.user_id == assignee_id)
            base_q = base_q.where(Brief.id.in_(sub))

        count_q = select(func.count()).select_from(base_q.subquery())
        total = (await self.db.execute(count_q)).scalar_one()

        items_q = base_q.order_by(Brief.created_at.desc()).offset(offset).limit(limit)
        rows = (await self.db.execute(items_q)).scalars().all()
        return list(rows), total

    async def create(self, data: dict[str, Any]) -> Brief:
        brief = Brief(**data)
        self.db.add(brief)
        await self.db.flush()
        await self.db.refresh(brief)
        return brief

    async def update(self, brief: Brief, data: dict[str, Any]) -> Brief:
        for key, val in data.items():
            setattr(brief, key, val)
        await self.db.flush()
        await self.db.refresh(brief)
        return brief

    async def soft_delete(self, brief: Brief) -> None:
        from datetime import UTC, datetime

        brief.deleted_at = datetime.now(UTC)
        await self.db.flush()


class BriefFieldValueRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_for_brief(self, brief_id: uuid.UUID) -> list[BriefFieldValue]:
        result = await self.db.execute(
            select(BriefFieldValue).where(BriefFieldValue.brief_id == brief_id)
        )
        return list(result.scalars().all())

    async def upsert_many(self, brief_id: uuid.UUID, values: list[dict[str, Any]]) -> None:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from app.models.brief import BriefFieldValue as BriefFieldValueModel

        for item in values:
            stmt = (
                pg_insert(BriefFieldValueModel)
                .values(
                    id=uuid.uuid4(),
                    brief_id=brief_id,
                    template_field_id=item["template_field_id"],
                    value=item["value"],
                )
                .on_conflict_do_update(
                    constraint="uq_brief_field_value",
                    set_={"value": item["value"]},
                )
            )
            await self.db.execute(stmt)
        await self.db.flush()


class BriefAssigneeRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_for_brief(self, brief_id: uuid.UUID) -> list[BriefAssignee]:
        result = await self.db.execute(
            select(BriefAssignee).where(BriefAssignee.brief_id == brief_id)
        )
        return list(result.scalars().all())

    async def add(
        self, brief_id: uuid.UUID, user_id: uuid.UUID, role_label: str | None
    ) -> BriefAssignee:
        assignee = BriefAssignee(brief_id=brief_id, user_id=user_id, role_label=role_label)
        self.db.add(assignee)
        await self.db.flush()
        await self.db.refresh(assignee)
        return assignee

    async def remove(self, brief_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(BriefAssignee).where(
                and_(
                    BriefAssignee.brief_id == brief_id,
                    BriefAssignee.user_id == user_id,
                )
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            return False
        await self.db.delete(row)
        await self.db.flush()
        return True

    async def exists(self, brief_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(BriefAssignee).where(
                and_(
                    BriefAssignee.brief_id == brief_id,
                    BriefAssignee.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none() is not None

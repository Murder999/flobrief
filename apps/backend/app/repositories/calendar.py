from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calendar import (
    CalendarItem,
    CalendarItemAsset,
    CalendarItemAssignee,
    CalendarItemStatusHistory,
)


class CalendarItemRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: dict) -> CalendarItem:
        obj = CalendarItem(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def get_by_id(self, item_id: uuid.UUID, agency_id: uuid.UUID) -> CalendarItem | None:
        result = await self.db.execute(
            select(CalendarItem).where(
                CalendarItem.id == item_id,
                CalendarItem.agency_id == agency_id,
                CalendarItem.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def update(self, item: CalendarItem, data: dict) -> CalendarItem:
        for key, value in data.items():
            setattr(item, key, value)
        await self.db.flush()
        return item

    async def get_by_brief_id(self, brief_id: uuid.UUID) -> CalendarItem | None:
        result = await self.db.execute(
            select(CalendarItem)
            .where(
                CalendarItem.brief_id == brief_id,
                CalendarItem.deleted_at.is_(None),
            )
            .order_by(CalendarItem.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_range(
        self,
        agency_id: uuid.UUID,
        start_dt: datetime,
        end_dt: datetime,
        brand_id: uuid.UUID | None = None,
        platform: str | None = None,
        status: str | None = None,
        assignee_id: uuid.UUID | None = None,
    ) -> list[CalendarItem]:
        date_filter = or_(
            and_(CalendarItem.publish_at >= start_dt, CalendarItem.publish_at <= end_dt),
            and_(CalendarItem.due_at >= start_dt, CalendarItem.due_at <= end_dt),
        )
        conditions = [
            CalendarItem.agency_id == agency_id,
            CalendarItem.deleted_at.is_(None),
            date_filter,
        ]
        if brand_id:
            conditions.append(CalendarItem.brand_id == brand_id)
        if platform:
            conditions.append(CalendarItem.platform == platform)
        if status:
            conditions.append(CalendarItem.status == status)

        stmt = (
            select(CalendarItem)
            .where(and_(*conditions))
            .order_by(
                CalendarItem.publish_at.asc().nulls_last(),
                CalendarItem.due_at.asc().nulls_last(),
            )
        )

        if assignee_id:
            stmt = stmt.join(
                CalendarItemAssignee,
                and_(
                    CalendarItemAssignee.calendar_item_id == CalendarItem.id,
                    CalendarItemAssignee.user_id == assignee_id,
                    CalendarItemAssignee.deleted_at.is_(None),
                ),
            )

        result = await self.db.execute(stmt)
        return list(result.scalars().unique().all())

    async def list_all(
        self,
        agency_id: uuid.UUID,
        brand_id: uuid.UUID | None = None,
        platform: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CalendarItem]:
        conditions = [
            CalendarItem.agency_id == agency_id,
            CalendarItem.deleted_at.is_(None),
        ]
        if brand_id:
            conditions.append(CalendarItem.brand_id == brand_id)
        if platform:
            conditions.append(CalendarItem.platform == platform)
        if status:
            conditions.append(CalendarItem.status == status)

        result = await self.db.execute(
            select(CalendarItem)
            .where(and_(*conditions))
            .order_by(CalendarItem.publish_at.asc().nulls_last())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())


class CalendarItemAssetRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: dict) -> CalendarItemAsset:
        obj = CalendarItemAsset(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def list_for_item(self, item_id: uuid.UUID) -> list[CalendarItemAsset]:
        result = await self.db.execute(
            select(CalendarItemAsset).where(
                CalendarItemAsset.calendar_item_id == item_id,
                CalendarItemAsset.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def get(self, item_id: uuid.UUID, asset_id: uuid.UUID) -> CalendarItemAsset | None:
        result = await self.db.execute(
            select(CalendarItemAsset).where(
                CalendarItemAsset.calendar_item_id == item_id,
                CalendarItemAsset.asset_id == asset_id,
                CalendarItemAsset.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def hard_delete(self, obj: CalendarItemAsset) -> None:
        await self.db.delete(obj)
        await self.db.flush()


class CalendarItemAssigneeRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: dict) -> CalendarItemAssignee:
        obj = CalendarItemAssignee(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def list_for_item(self, item_id: uuid.UUID) -> list[CalendarItemAssignee]:
        result = await self.db.execute(
            select(CalendarItemAssignee).where(
                CalendarItemAssignee.calendar_item_id == item_id,
                CalendarItemAssignee.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def get(self, item_id: uuid.UUID, user_id: uuid.UUID) -> CalendarItemAssignee | None:
        result = await self.db.execute(
            select(CalendarItemAssignee).where(
                CalendarItemAssignee.calendar_item_id == item_id,
                CalendarItemAssignee.user_id == user_id,
                CalendarItemAssignee.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def hard_delete(self, obj: CalendarItemAssignee) -> None:
        await self.db.delete(obj)
        await self.db.flush()


class CalendarItemStatusHistoryRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: dict) -> CalendarItemStatusHistory:
        obj = CalendarItemStatusHistory(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def list_for_item(self, item_id: uuid.UUID) -> list[CalendarItemStatusHistory]:
        result = await self.db.execute(
            select(CalendarItemStatusHistory)
            .where(CalendarItemStatusHistory.calendar_item_id == item_id)
            .order_by(CalendarItemStatusHistory.created_at.asc())
        )
        return list(result.scalars().all())

from __future__ import annotations

import uuid
from calendar import monthrange
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext
from app.models.asset import Asset
from app.models.brand import Brand
from app.models.brief import Brief
from app.models.calendar import CalendarItem
from app.repositories.activity import ActivityLogRepository
from app.repositories.calendar import (
    CalendarItemAssetRepository,
    CalendarItemAssigneeRepository,
    CalendarItemRepository,
    CalendarItemStatusHistoryRepository,
)
from app.schemas.calendar import (
    CalendarItemAssetRead,
    CalendarItemAssigneeRead,
    CalendarItemCreate,
    CalendarItemDetail,
    CalendarItemRead,
    CalendarItemUpdate,
    StatusChangeRequest,
)


class CalendarService:
    def __init__(self, db: AsyncSession, workspace: WorkspaceContext) -> None:
        self.db = db
        self.workspace = workspace
        self.item_repo = CalendarItemRepository(db)
        self.asset_repo = CalendarItemAssetRepository(db)
        self.assignee_repo = CalendarItemAssigneeRepository(db)
        self.history_repo = CalendarItemStatusHistoryRepository(db)
        self._activity = ActivityLogRepository(db)

    # ── Validation helpers ────────────────────────────────────────────────────

    async def _require_item(self, item_id: uuid.UUID) -> CalendarItem:
        item = await self.item_repo.get_by_id(item_id, self.workspace.agency.id)
        if not item:
            raise HTTPException(status_code=404, detail="Calendar item not found")
        return item

    async def _validate_brand(self, brand_id: uuid.UUID) -> None:
        result = await self.db.execute(
            select(Brand).where(
                Brand.id == brand_id,
                Brand.agency_id == self.workspace.agency.id,
                Brand.deleted_at.is_(None),
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Brand not found in this agency")

    async def _validate_brief(self, brief_id: uuid.UUID) -> None:
        result = await self.db.execute(
            select(Brief).where(
                Brief.id == brief_id,
                Brief.agency_id == self.workspace.agency.id,
                Brief.deleted_at.is_(None),
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Brief not found in this agency")

    async def _validate_asset(self, asset_id: uuid.UUID) -> None:
        result = await self.db.execute(
            select(Asset).where(
                Asset.id == asset_id,
                Asset.agency_id == self.workspace.agency.id,
                Asset.deleted_at.is_(None),
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Asset not found in this agency")

    async def _build_detail(self, item: CalendarItem) -> CalendarItemDetail:
        assets = await self.asset_repo.list_for_item(item.id)
        assignees = await self.assignee_repo.list_for_item(item.id)
        history = await self.history_repo.list_for_item(item.id)
        detail = CalendarItemDetail.model_validate(item)
        return detail.model_copy(
            update={
                "assets": [CalendarItemAssetRead.model_validate(a) for a in assets],
                "assignees": [CalendarItemAssigneeRead.model_validate(a) for a in assignees],
                "status_history": [
                    {
                        "id": h.id,
                        "calendar_item_id": h.calendar_item_id,
                        "old_status": h.old_status,
                        "new_status": h.new_status,
                        "changed_by_id": h.changed_by_id,
                        "created_at": h.created_at,
                    }
                    for h in history
                ],
            }
        )

    # ── CRUD ──────────────────────────────────────────────────────────────────

    async def create(self, payload: CalendarItemCreate) -> CalendarItemRead:
        if payload.brand_id:
            await self._validate_brand(payload.brand_id)
        if payload.brief_id:
            await self._validate_brief(payload.brief_id)

        item = await self.item_repo.create(
            {
                "agency_id": self.workspace.agency.id,
                "brand_id": payload.brand_id,
                "brief_id": payload.brief_id,
                "title": payload.title,
                "description": payload.description,
                "item_type": payload.item_type,
                "platform": payload.platform,
                "status": payload.status,
                "priority": payload.priority,
                "milestone_type": payload.milestone_type,
                "publish_at": payload.publish_at,
                "due_at": payload.due_at,
                "color_label": payload.color_label,
                "created_by_id": self.workspace.user.id,
            }
        )

        await self.history_repo.create(
            {
                "calendar_item_id": item.id,
                "old_status": None,
                "new_status": payload.status,
                "changed_by_id": self.workspace.user.id,
            }
        )
        await self._activity.create(
            action="calendar_item.created",
            entity_type="calendar_item",
            entity_id=item.id,
            agency_id=self.workspace.agency.id,
            brand_id=payload.brand_id,
            actor_user_id=self.workspace.user.id,
            meta={"title": payload.title, "platform": payload.platform},
        )

        await self.db.commit()
        await self.db.refresh(item)
        return CalendarItemRead.model_validate(item)

    async def get(self, item_id: uuid.UUID) -> CalendarItemDetail:
        item = await self._require_item(item_id)
        return await self._build_detail(item)

    async def update(self, item_id: uuid.UUID, payload: CalendarItemUpdate) -> CalendarItemRead:
        item = await self._require_item(item_id)
        if payload.brand_id is not None:
            await self._validate_brand(payload.brand_id)
        if payload.brief_id is not None:
            await self._validate_brief(payload.brief_id)

        data = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
        data["updated_by_id"] = self.workspace.user.id

        await self.item_repo.update(item, data)
        await self.db.commit()
        await self.db.refresh(item)
        return CalendarItemRead.model_validate(item)

    async def delete(self, item_id: uuid.UUID) -> None:
        item = await self._require_item(item_id)
        item.soft_delete()
        await self.db.commit()

    async def change_status(
        self, item_id: uuid.UUID, payload: StatusChangeRequest
    ) -> CalendarItemRead:
        item = await self._require_item(item_id)
        old_status = item.status

        if old_status == payload.new_status:
            return CalendarItemRead.model_validate(item)

        await self.item_repo.update(
            item,
            {
                "status": payload.new_status,
                "updated_by_id": self.workspace.user.id,
            },
        )

        await self.history_repo.create(
            {
                "calendar_item_id": item.id,
                "old_status": old_status,
                "new_status": payload.new_status,
                "changed_by_id": self.workspace.user.id,
            }
        )

        await self.db.commit()
        await self.db.refresh(item)
        return CalendarItemRead.model_validate(item)

    # ── Asset attachments ─────────────────────────────────────────────────────

    async def attach_asset(self, item_id: uuid.UUID, asset_id: uuid.UUID) -> CalendarItemAssetRead:
        await self._require_item(item_id)
        await self._validate_asset(asset_id)

        existing = await self.asset_repo.get(item_id, asset_id)
        if existing:
            return CalendarItemAssetRead.model_validate(existing)

        link = await self.asset_repo.create(
            {
                "calendar_item_id": item_id,
                "asset_id": asset_id,
            }
        )
        await self.db.commit()
        await self.db.refresh(link)
        return CalendarItemAssetRead.model_validate(link)

    async def detach_asset(self, item_id: uuid.UUID, asset_id: uuid.UUID) -> None:
        await self._require_item(item_id)
        link = await self.asset_repo.get(item_id, asset_id)
        if not link:
            raise HTTPException(status_code=404, detail="Asset not attached to this item")
        await self.asset_repo.hard_delete(link)
        await self.db.commit()

    # ── Assignees ─────────────────────────────────────────────────────────────

    async def assign_user(self, item_id: uuid.UUID, user_id: uuid.UUID) -> CalendarItemAssigneeRead:
        await self._require_item(item_id)

        existing = await self.assignee_repo.get(item_id, user_id)
        if existing:
            return CalendarItemAssigneeRead.model_validate(existing)

        assignee = await self.assignee_repo.create(
            {
                "calendar_item_id": item_id,
                "user_id": user_id,
            }
        )
        await self.db.commit()
        await self.db.refresh(assignee)
        return CalendarItemAssigneeRead.model_validate(assignee)

    async def unassign_user(self, item_id: uuid.UUID, user_id: uuid.UUID) -> None:
        await self._require_item(item_id)
        assignee = await self.assignee_repo.get(item_id, user_id)
        if not assignee:
            raise HTTPException(status_code=404, detail="User not assigned to this item")
        await self.assignee_repo.hard_delete(assignee)
        await self.db.commit()

    # ── Views ─────────────────────────────────────────────────────────────────

    async def list_month(
        self,
        year: int,
        month: int,
        brand_id: uuid.UUID | None = None,
        platform: str | None = None,
        status: str | None = None,
    ) -> list[CalendarItemRead]:
        _, last_day = monthrange(year, month)
        start_dt = datetime(year, month, 1, tzinfo=UTC)
        end_dt = datetime(year, month, last_day, 23, 59, 59, tzinfo=UTC)
        items = await self.item_repo.list_range(
            self.workspace.agency.id, start_dt, end_dt, brand_id, platform, status
        )
        return [CalendarItemRead.model_validate(i) for i in items]

    async def list_week(
        self,
        year: int,
        week: int,
        brand_id: uuid.UUID | None = None,
        platform: str | None = None,
        status: str | None = None,
    ) -> list[CalendarItemRead]:
        jan1 = datetime(year, 1, 1, tzinfo=UTC)
        start_dt = jan1 + timedelta(weeks=week - 1) - timedelta(days=jan1.weekday())
        end_dt = start_dt + timedelta(days=6, hours=23, minutes=59, seconds=59)
        items = await self.item_repo.list_range(
            self.workspace.agency.id, start_dt, end_dt, brand_id, platform, status
        )
        return [CalendarItemRead.model_validate(i) for i in items]

    async def list_all(
        self,
        brand_id: uuid.UUID | None = None,
        platform: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CalendarItemRead]:
        items = await self.item_repo.list_all(
            self.workspace.agency.id, brand_id, platform, status, limit, offset
        )
        return [CalendarItemRead.model_validate(i) for i in items]

    # ── Brief link ────────────────────────────────────────────────────────────

    async def link_brief(self, item_id: uuid.UUID, brief_id: uuid.UUID) -> CalendarItemRead:
        item = await self._require_item(item_id)
        await self._validate_brief(brief_id)
        await self.item_repo.update(
            item,
            {
                "brief_id": brief_id,
                "updated_by_id": self.workspace.user.id,
            },
        )
        await self.db.commit()
        await self.db.refresh(item)
        return CalendarItemRead.model_validate(item)

    async def unlink_brief(self, item_id: uuid.UUID) -> CalendarItemRead:
        item = await self._require_item(item_id)
        await self.item_repo.update(
            item,
            {
                "brief_id": None,
                "updated_by_id": self.workspace.user.id,
            },
        )
        await self.db.commit()
        await self.db.refresh(item)
        return CalendarItemRead.model_validate(item)

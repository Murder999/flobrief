from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deliverable_preview import DeliverablePreviewConfig, DeliverablePreviewSlot


class DeliverablePreviewConfigRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_deliverable(
        self, deliverable_id: uuid.UUID, agency_id: uuid.UUID
    ) -> DeliverablePreviewConfig | None:
        result = await self.db.execute(
            select(DeliverablePreviewConfig).where(
                DeliverablePreviewConfig.deliverable_id == deliverable_id,
                DeliverablePreviewConfig.agency_id == agency_id,
                DeliverablePreviewConfig.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        deliverable_id: uuid.UUID,
        agency_id: uuid.UUID,
        brand_id: uuid.UUID | None,
        brief_id: uuid.UUID,
        data: dict,
        actor_user_id: uuid.UUID,
    ) -> DeliverablePreviewConfig:
        existing = await self.get_by_deliverable(deliverable_id, agency_id)
        if existing is None:
            config = DeliverablePreviewConfig(
                agency_id=agency_id,
                brand_id=brand_id,
                brief_id=brief_id,
                deliverable_id=deliverable_id,
                created_by_id=actor_user_id,
                updated_by_id=actor_user_id,
                revision_number=1,
                **data,
            )
            self.db.add(config)
        else:
            for key, value in data.items():
                setattr(existing, key, value)
            existing.updated_by_id = actor_user_id
            existing.revision_number += 1
            config = existing
        await self.db.flush()
        return config


class DeliverablePreviewSlotRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_for_deliverable(self, deliverable_id: uuid.UUID) -> list[DeliverablePreviewSlot]:
        result = await self.db.execute(
            select(DeliverablePreviewSlot)
            .where(
                DeliverablePreviewSlot.deliverable_id == deliverable_id,
                DeliverablePreviewSlot.deleted_at.is_(None),
            )
            .order_by(DeliverablePreviewSlot.position.asc())
        )
        return list(result.scalars().all())

    async def replace_all(
        self,
        deliverable_id: uuid.UUID,
        slots: list[dict],
    ) -> list[DeliverablePreviewSlot]:
        """Delete-then-recreate — avoids transient unique-constraint collisions
        when positions are being swapped, and keeps ordering an explicit,
        controlled write rather than a partial in-place patch."""
        existing = await self.list_for_deliverable(deliverable_id)
        for row in existing:
            await self.db.delete(row)
        await self.db.flush()

        created: list[DeliverablePreviewSlot] = []
        for item in slots:
            slot = DeliverablePreviewSlot(deliverable_id=deliverable_id, **item)
            self.db.add(slot)
            created.append(slot)
        await self.db.flush()
        created.sort(key=lambda s: s.position)
        return created

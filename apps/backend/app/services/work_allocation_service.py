"""WorkAllocationService: CRUD for manual WorkAllocation rows (plan §3/§7).
`end_date >= start_date` and `allocated_minutes > 0` are already enforced by
the Pydantic schema (`WorkAllocationCreate`/`Update`) and the DB check
constraints — this service adds the one thing neither of those layers can
do: a non-blocking over-capacity warning computed against the affected
user's real net capacity via `CapacityCalculationService`."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.work_allocation import WorkAllocation
from app.repositories.work_allocation import WorkAllocationRepository
from app.schemas.work_allocation import WorkAllocationCreate, WorkAllocationUpdate
from app.services.capacity_calculation_service import CapacityCalculationService

_OVER_CAPACITY_THRESHOLD_PCT = 100


class WorkAllocationService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = WorkAllocationRepository(db)
        self._capacity = CapacityCalculationService(db)

    async def _over_capacity_warning(
        self, agency_id: uuid.UUID, user_id: uuid.UUID, start_date: date, end_date: date
    ) -> bool:
        report = await self._capacity.user_capacity(agency_id, user_id, start_date, end_date)
        return report.planned_utilization_pct > _OVER_CAPACITY_THRESHOLD_PCT

    async def create(
        self,
        agency_id: uuid.UUID,
        created_by_id: uuid.UUID,
        data: WorkAllocationCreate,
    ) -> tuple[WorkAllocation, bool]:
        obj = await self._repo.create(
            {
                "agency_id": agency_id,
                "brand_id": data.brand_id,
                "brief_id": data.brief_id,
                "task_id": data.task_id,
                "deliverable_id": data.deliverable_id,
                "user_id": data.user_id,
                "category": data.category,
                "start_date": data.start_date,
                "end_date": data.end_date,
                "allocated_minutes": data.allocated_minutes,
                "allocation_source": data.allocation_source,
                "locked": data.locked,
                "created_by_id": created_by_id,
            }
        )
        await self._db.commit()
        await self._db.refresh(obj)

        warning = await self._over_capacity_warning(
            agency_id, obj.user_id, obj.start_date, obj.end_date
        )
        return obj, warning

    async def update(
        self,
        agency_id: uuid.UUID,
        allocation_id: uuid.UUID,
        data: WorkAllocationUpdate,
    ) -> tuple[WorkAllocation, bool]:
        obj = await self._repo.get_by_id(allocation_id, agency_id)
        if obj is None:
            raise NotFoundError("Kapasite ataması", str(allocation_id))

        update_data = data.model_dump(exclude_unset=True, exclude_none=True)
        new_start = update_data.get("start_date", obj.start_date)
        new_end = update_data.get("end_date", obj.end_date)
        if new_end < new_start:
            raise ValidationError("Bitiş tarihi başlangıçtan önce olamaz")

        updated = await self._repo.update(obj, update_data)
        await self._db.commit()
        await self._db.refresh(updated)

        warning = await self._over_capacity_warning(
            agency_id, updated.user_id, updated.start_date, updated.end_date
        )
        return updated, warning

    async def delete(self, agency_id: uuid.UUID, allocation_id: uuid.UUID) -> None:
        obj = await self._repo.get_by_id(allocation_id, agency_id)
        if obj is None:
            raise NotFoundError("Kapasite ataması", str(allocation_id))
        await self._repo.soft_delete(obj)
        await self._db.commit()

    async def get(self, agency_id: uuid.UUID, allocation_id: uuid.UUID) -> WorkAllocation:
        obj = await self._repo.get_by_id(allocation_id, agency_id)
        if obj is None:
            raise NotFoundError("Kapasite ataması", str(allocation_id))
        return obj

    async def list_for_user(
        self,
        agency_id: uuid.UUID,
        user_id: uuid.UUID,
        start: date | None = None,
        end: date | None = None,
    ) -> list[WorkAllocation]:
        return await self._repo.list_for_user(agency_id, user_id, start, end)

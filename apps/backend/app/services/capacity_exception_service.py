"""CapacityExceptionService: simple CRUD for ad-hoc, single-date capacity
overrides (reduced/increased/closure). One active exception per (user, date)
is enforced by the DB's partial unique index; the service checks first only
to raise a clean, actionable error instead of a bare IntegrityError."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.capacity_exception import CapacityException
from app.repositories.capacity_exception import CapacityExceptionRepository
from app.schemas.capacity_exception import CapacityExceptionCreate, CapacityExceptionUpdate


class CapacityExceptionService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = CapacityExceptionRepository(db)

    async def create(
        self,
        agency_id: uuid.UUID,
        created_by_id: uuid.UUID,
        data: CapacityExceptionCreate,
    ) -> CapacityException:
        existing = await self._repo.get_for_user_date(agency_id, data.user_id, data.date)
        if existing is not None:
            raise ConflictError("Bu kullanıcı için bu tarihte zaten bir kapasite istisnası var")

        obj = await self._repo.create(
            {
                "agency_id": agency_id,
                "user_id": data.user_id,
                "date": data.date,
                "capacity_minutes": data.capacity_minutes,
                "reason": data.reason,
                "exception_type": data.exception_type,
                "created_by_id": created_by_id,
            }
        )
        await self._db.commit()
        await self._db.refresh(obj)
        return obj

    async def update(
        self,
        agency_id: uuid.UUID,
        exception_id: uuid.UUID,
        data: CapacityExceptionUpdate,
    ) -> CapacityException:
        obj = await self._repo.get_by_id(exception_id, agency_id)
        if obj is None:
            raise NotFoundError("Kapasite istisnası", str(exception_id))
        update_data = data.model_dump(exclude_unset=True, exclude_none=True)
        updated = await self._repo.update(obj, update_data)
        await self._db.commit()
        await self._db.refresh(updated)
        return updated

    async def delete(self, agency_id: uuid.UUID, exception_id: uuid.UUID) -> None:
        obj = await self._repo.get_by_id(exception_id, agency_id)
        if obj is None:
            raise NotFoundError("Kapasite istisnası", str(exception_id))
        await self._repo.soft_delete(obj)
        await self._db.commit()

    async def list_for_user(
        self,
        agency_id: uuid.UUID,
        user_id: uuid.UUID,
        start: date | None = None,
        end: date | None = None,
    ) -> list[CapacityException]:
        return await self._repo.list_for_user(agency_id, user_id, start, end)

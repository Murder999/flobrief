"""AgencySettingsService: get-or-create the single AgencySettings row per
agency, and the threshold/currency/sequence accessors every future
capacity/finance service builds on. Defaults (60/85/100/"TRY"/30/0/False)
only ever come from the model's column defaults — never re-declared here."""

from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agency_settings import AgencySettings
from app.repositories.agency_settings import AgencySettingsRepository
from app.schemas.agency_settings import AgencySettingsUpdate


class AgencySettingsService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = AgencySettingsRepository(db)

    async def get_or_create(self, agency_id: uuid.UUID) -> AgencySettings:
        settings = await self._repo.get_by_agency(agency_id)
        if settings is not None:
            return settings

        try:
            settings = await self._repo.create({"agency_id": agency_id})
            await self._db.commit()
        except IntegrityError:
            # Concurrent get-or-create race: another request created the row
            # first — the unique constraint on agency_id is the actual
            # correctness boundary, this is just a clean fallback read.
            await self._db.rollback()
            settings = await self._repo.get_by_agency(agency_id)
            if settings is None:
                raise
            return settings

        await self._db.refresh(settings)
        return settings

    async def update(
        self,
        agency_id: uuid.UUID,
        data: AgencySettingsUpdate,
        updated_by_id: uuid.UUID,
    ) -> AgencySettings:
        settings = await self.get_or_create(agency_id)
        update_data = data.model_dump(exclude_unset=True, exclude_none=True)
        update_data["updated_by_id"] = updated_by_id
        updated = await self._repo.update(settings, update_data)
        await self._db.commit()
        await self._db.refresh(updated)
        return updated

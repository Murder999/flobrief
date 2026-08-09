from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting_connector import AccountingConnector


class AccountingConnectorRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(
        self, connector_id: uuid.UUID, agency_id: uuid.UUID
    ) -> AccountingConnector | None:
        result = await self.db.execute(
            select(AccountingConnector).where(
                AccountingConnector.id == connector_id,
                AccountingConnector.agency_id == agency_id,
                AccountingConnector.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_provider(
        self, agency_id: uuid.UUID, provider: str
    ) -> AccountingConnector | None:
        result = await self.db.execute(
            select(AccountingConnector).where(
                AccountingConnector.agency_id == agency_id,
                AccountingConnector.provider == provider,
                AccountingConnector.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_agency(self, agency_id: uuid.UUID) -> list[AccountingConnector]:
        result = await self.db.execute(
            select(AccountingConnector)
            .where(
                AccountingConnector.agency_id == agency_id,
                AccountingConnector.deleted_at.is_(None),
            )
            .order_by(AccountingConnector.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(self, data: dict) -> AccountingConnector:
        obj = AccountingConnector(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def update(self, obj: AccountingConnector, data: dict) -> AccountingConnector:
        for key, value in data.items():
            setattr(obj, key, value)
        await self.db.flush()
        return obj

    async def soft_delete(self, obj: AccountingConnector) -> None:
        obj.soft_delete()
        await self.db.flush()

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting_connector import ConnectorSyncLog


class ConnectorSyncLogRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_idempotency_key(self, idempotency_key: str) -> ConnectorSyncLog | None:
        result = await self.db.execute(
            select(ConnectorSyncLog).where(
                ConnectorSyncLog.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_connector(
        self, connector_id: uuid.UUID, agency_id: uuid.UUID, limit: int = 50
    ) -> list[ConnectorSyncLog]:
        result = await self.db.execute(
            select(ConnectorSyncLog)
            .where(
                ConnectorSyncLog.connector_id == connector_id,
                ConnectorSyncLog.agency_id == agency_id,
            )
            .order_by(ConnectorSyncLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, data: dict) -> ConnectorSyncLog:
        obj = ConnectorSyncLog(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def update(self, obj: ConnectorSyncLog, data: dict) -> ConnectorSyncLog:
        for key, value in data.items():
            setattr(obj, key, value)
        await self.db.flush()
        return obj

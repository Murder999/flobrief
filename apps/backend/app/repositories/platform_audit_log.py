from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.models.platform_audit_log import PlatformAuditLog


class PlatformAuditLogRepository:
    """INSERT-only repository for platform_audit_logs.

    update() and delete() are intentionally absent. Immutability is also
    enforced at the DB level via a trigger (see initial migration).
    """

    def __init__(self, session: Any) -> None:
        self.session = session

    async def create(
        self,
        *,
        admin_user_id: UUID,
        action: str,
        target_type: str | None = None,
        target_id: UUID | None = None,
        target_tenant_type: str | None = None,
        target_tenant_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        meta: dict | None = None,
    ) -> PlatformAuditLog:
        log = PlatformAuditLog(
            admin_user_id=admin_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_tenant_type=target_tenant_type,
            target_tenant_id=target_tenant_id,
            ip_address=ip_address,
            user_agent=user_agent,
            meta=meta,
        )
        self.session.add(log)
        await self.session.flush()
        await self.session.refresh(log)
        return log

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[PlatformAuditLog]:
        stmt = (
            select(PlatformAuditLog)
            .order_by(PlatformAuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_admin(
        self, admin_user_id: UUID, *, limit: int = 50
    ) -> list[PlatformAuditLog]:
        stmt = (
            select(PlatformAuditLog)
            .where(PlatformAuditLog.admin_user_id == admin_user_id)
            .order_by(PlatformAuditLog.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

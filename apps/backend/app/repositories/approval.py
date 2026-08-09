from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import (
    Approval,
    ApprovalComment,
    ApprovalEvent,
    ApprovalToken,
    BriefChangeLog,
    BriefVersion,
)


class BriefVersionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def next_version_number(self, brief_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.max(BriefVersion.version_number)).where(BriefVersion.brief_id == brief_id)
        )
        current = result.scalar_one_or_none()
        return (current or 0) + 1

    async def create(self, data: dict[str, Any]) -> BriefVersion:
        version = BriefVersion(**data)
        self.db.add(version)
        await self.db.flush()
        await self.db.refresh(version)
        return version

    async def list_for_brief(self, brief_id: uuid.UUID) -> list[BriefVersion]:
        result = await self.db.execute(
            select(BriefVersion)
            .where(BriefVersion.brief_id == brief_id)
            .order_by(BriefVersion.version_number.asc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, version_id: uuid.UUID, brief_id: uuid.UUID) -> BriefVersion | None:
        result = await self.db.execute(
            select(BriefVersion).where(
                and_(
                    BriefVersion.id == version_id,
                    BriefVersion.brief_id == brief_id,
                )
            )
        )
        return result.scalar_one_or_none()


class BriefChangeLogRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: dict[str, Any]) -> BriefChangeLog:
        log = BriefChangeLog(**data)
        self.db.add(log)
        await self.db.flush()
        return log

    async def list_for_brief(self, brief_id: uuid.UUID) -> list[BriefChangeLog]:
        result = await self.db.execute(
            select(BriefChangeLog)
            .where(BriefChangeLog.brief_id == brief_id)
            .order_by(BriefChangeLog.created_at.desc())
        )
        return list(result.scalars().all())


class ApprovalRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: dict[str, Any]) -> Approval:
        approval = Approval(**data)
        self.db.add(approval)
        await self.db.flush()
        await self.db.refresh(approval)
        return approval

    async def get_by_id(self, approval_id: uuid.UUID, brief_id: uuid.UUID) -> Approval | None:
        result = await self.db.execute(
            select(Approval).where(
                and_(
                    Approval.id == approval_id,
                    Approval.brief_id == brief_id,
                    Approval.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_for_brief(self, brief_id: uuid.UUID) -> list[Approval]:
        result = await self.db.execute(
            select(Approval)
            .where(and_(Approval.brief_id == brief_id, Approval.deleted_at.is_(None)))
            .order_by(Approval.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, approval: Approval, data: dict[str, Any]) -> Approval:
        for key, val in data.items():
            setattr(approval, key, val)
        await self.db.flush()
        await self.db.refresh(approval)
        return approval


class ApprovalTokenRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: dict[str, Any]) -> ApprovalToken:
        token = ApprovalToken(**data)
        self.db.add(token)
        await self.db.flush()
        await self.db.refresh(token)
        return token

    async def get_by_hash(self, token_hash: str) -> ApprovalToken | None:
        result = await self.db.execute(
            select(ApprovalToken).where(ApprovalToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def get_approval(self, token: ApprovalToken) -> Approval | None:
        result = await self.db.execute(
            select(Approval).where(
                and_(Approval.id == token.approval_id, Approval.deleted_at.is_(None))
            )
        )
        return result.scalar_one_or_none()

    async def update(self, token: ApprovalToken, data: dict[str, Any]) -> ApprovalToken:
        for key, val in data.items():
            setattr(token, key, val)
        await self.db.flush()
        return token


class ApprovalEventRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: dict[str, Any]) -> ApprovalEvent:
        event = ApprovalEvent(**data)
        self.db.add(event)
        await self.db.flush()
        return event


class ApprovalCommentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: dict[str, Any]) -> ApprovalComment:
        comment = ApprovalComment(**data)
        self.db.add(comment)
        await self.db.flush()
        await self.db.refresh(comment)
        return comment

    async def list_for_approval(
        self, approval_id: uuid.UUID, *, include_internal: bool = False
    ) -> list[ApprovalComment]:
        q = select(ApprovalComment).where(
            and_(
                ApprovalComment.approval_id == approval_id,
                ApprovalComment.deleted_at.is_(None),
            )
        )
        if not include_internal:
            q = q.where(ApprovalComment.is_internal.is_(False))
        result = await self.db.execute(q.order_by(ApprovalComment.created_at.asc()))
        return list(result.scalars().all())

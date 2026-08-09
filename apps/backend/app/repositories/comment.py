from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment import Comment, CommentThread


class CommentThreadRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: dict) -> CommentThread:
        obj = CommentThread(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def get_by_id(self, thread_id: uuid.UUID) -> CommentThread | None:
        result = await self.db.execute(
            select(CommentThread).where(
                CommentThread.id == thread_id,
                CommentThread.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_brief(
        self, brief_id: uuid.UUID, agency_id: uuid.UUID
    ) -> list[CommentThread]:
        result = await self.db.execute(
            select(CommentThread)
            .where(
                CommentThread.brief_id == brief_id,
                CommentThread.agency_id == agency_id,
                CommentThread.deleted_at.is_(None),
            )
            .order_by(CommentThread.created_at)
        )
        return list(result.scalars().all())

    async def update(self, thread: CommentThread, data: dict) -> CommentThread:
        for key, value in data.items():
            setattr(thread, key, value)
        await self.db.flush()
        return thread


class CommentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: dict) -> Comment:
        obj = Comment(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def get_by_id(self, comment_id: uuid.UUID) -> Comment | None:
        result = await self.db.execute(
            select(Comment).where(
                Comment.id == comment_id,
                Comment.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_thread(
        self,
        thread_id: uuid.UUID,
        visibility: str | None = None,
    ) -> list[Comment]:
        q = (
            select(Comment)
            .where(
                Comment.thread_id == thread_id,
                Comment.deleted_at.is_(None),
            )
            .order_by(Comment.created_at)
        )
        if visibility is not None:
            q = q.where(Comment.visibility == visibility)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def update(self, comment: Comment, data: dict) -> Comment:
        for key, value in data.items():
            setattr(comment, key, value)
        await self.db.flush()
        return comment

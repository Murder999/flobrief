from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseRepository(Generic[T]):
    model: type[T]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, id: UUID) -> T | None:
        stmt = select(self.model).where(
            self.model.id == id,
            self.model.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[T]:
        stmt = (
            select(self.model)
            .where(self.model.deleted_at.is_(None))
            .order_by(self.model.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, **kwargs: Any) -> T:
        obj = self.model(**kwargs)
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def update(self, obj: T, **kwargs: Any) -> T:
        for key, value in kwargs.items():
            setattr(obj, key, value)
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def soft_delete(self, obj: T) -> None:
        obj.soft_delete()
        self.session.add(obj)
        await self.session.flush()

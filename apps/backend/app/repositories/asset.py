from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset, AssetLink, AssetVersion


class AssetRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: dict) -> Asset:
        obj = Asset(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def get_by_id(self, asset_id: uuid.UUID, agency_id: uuid.UUID) -> Asset | None:
        result = await self.db.execute(
            select(Asset).where(
                Asset.id == asset_id,
                Asset.agency_id == agency_id,
                Asset.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_brief(self, brief_id: uuid.UUID, agency_id: uuid.UUID) -> list[Asset]:
        # Filter by a subquery of linked asset ids rather than joining AssetLink
        # directly — a brief can have more than one AssetLink row pointing at the
        # same asset (e.g. it's linked both generally and to a deliverable), and
        # joining would return that Asset row once per matching link.
        linked_asset_ids = select(AssetLink.asset_id).where(
            AssetLink.brief_id == brief_id,
            AssetLink.deleted_at.is_(None),
        )
        result = await self.db.execute(
            select(Asset)
            .where(
                Asset.id.in_(linked_asset_ids),
                Asset.agency_id == agency_id,
                Asset.deleted_at.is_(None),
            )
            .order_by(Asset.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_for_brand_brief(
        self,
        brief_id: uuid.UUID,
        agency_id: uuid.UUID,
    ) -> list[Asset]:
        """Return only assets deliberately visible in the brand portal.

        The brief itself is tenant-checked by the service. A subquery keeps
        duplicate AssetLink rows from duplicating assets in the response.
        """
        linked_asset_ids = select(AssetLink.asset_id).where(
            AssetLink.brief_id == brief_id,
            AssetLink.deleted_at.is_(None),
        )
        result = await self.db.execute(
            select(Asset)
            .where(
                Asset.id.in_(linked_asset_ids),
                Asset.agency_id == agency_id,
                Asset.visibility.in_(("client_visible", "brand_reference")),
                Asset.deleted_at.is_(None),
            )
            .order_by(Asset.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, asset: Asset, data: dict) -> Asset:
        for key, value in data.items():
            setattr(asset, key, value)
        await self.db.flush()
        return asset


class AssetVersionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def next_version_number(self, asset_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.max(AssetVersion.version_number)).where(AssetVersion.asset_id == asset_id)
        )
        current_max = result.scalar_one_or_none()
        return (current_max or 0) + 1

    async def create(self, data: dict) -> AssetVersion:
        obj = AssetVersion(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def list_for_asset(self, asset_id: uuid.UUID) -> list[AssetVersion]:
        result = await self.db.execute(
            select(AssetVersion)
            .where(AssetVersion.asset_id == asset_id)
            .order_by(AssetVersion.version_number)
        )
        return list(result.scalars().all())


class AssetLinkRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: dict) -> AssetLink:
        obj = AssetLink(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def get_by_id(self, link_id: uuid.UUID) -> AssetLink | None:
        result = await self.db.execute(
            select(AssetLink).where(
                AssetLink.id == link_id,
                AssetLink.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def hard_delete(self, link: AssetLink) -> None:
        await self.db.delete(link)
        await self.db.flush()

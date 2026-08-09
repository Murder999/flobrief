from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_provider_settings import PlatformProviderSetting


class PlatformProviderSettingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_provider(self, provider: str) -> PlatformProviderSetting | None:
        result = await self.session.execute(
            select(PlatformProviderSetting).where(
                PlatformProviderSetting.provider == provider,
                PlatformProviderSetting.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def upsert(self, provider: str, **kwargs: Any) -> PlatformProviderSetting:
        """Get or create, then apply kwargs as attribute updates."""
        row = await self.get_by_provider(provider)
        if row is None:
            row = PlatformProviderSetting(provider=provider, **kwargs)
        else:
            for k, v in kwargs.items():
                setattr(row, k, v)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row

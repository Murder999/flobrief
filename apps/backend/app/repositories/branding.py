from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.branding import AgencyBrandingSettings, BrandingAsset, CustomDomainSettings


class BrandingSettingsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_agency(self, agency_id: uuid.UUID) -> AgencyBrandingSettings | None:
        result = await self.db.execute(
            select(AgencyBrandingSettings).where(
                AgencyBrandingSettings.agency_id == agency_id,
                AgencyBrandingSettings.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, agency_id: uuid.UUID) -> AgencyBrandingSettings:
        obj = AgencyBrandingSettings(agency_id=agency_id)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def update(self, settings: AgencyBrandingSettings, data: dict) -> AgencyBrandingSettings:
        for key, value in data.items():
            setattr(settings, key, value)
        await self.db.flush()
        return settings

    async def reset(self, settings: AgencyBrandingSettings) -> AgencyBrandingSettings:
        settings.brand_name_override = None
        settings.primary_color = None
        settings.secondary_color = None
        settings.accent_color = None
        settings.logo_asset_id = None
        settings.email_logo_asset_id = None
        settings.favicon_asset_id = None
        settings.custom_footer_text = None
        settings.is_white_label_enabled = False
        await self.db.flush()
        return settings


class BrandingAssetRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self, agency_id: uuid.UUID, asset_id: uuid.UUID, asset_type: str
    ) -> BrandingAsset:
        obj = BrandingAsset(agency_id=agency_id, asset_id=asset_id, asset_type=asset_type)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def is_branding_asset(self, asset_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(BrandingAsset).where(
                BrandingAsset.asset_id == asset_id,
                BrandingAsset.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none() is not None


class CustomDomainRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_agency(self, agency_id: uuid.UUID) -> CustomDomainSettings | None:
        result = await self.db.execute(
            select(CustomDomainSettings).where(
                CustomDomainSettings.agency_id == agency_id,
                CustomDomainSettings.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self, agency_id: uuid.UUID, domain: str, token_hash: str
    ) -> CustomDomainSettings:
        obj = CustomDomainSettings(
            agency_id=agency_id,
            domain=domain,
            status="pending",
            verification_token_hash=token_hash,
        )
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def update(self, domain: CustomDomainSettings, data: dict) -> CustomDomainSettings:
        for key, value in data.items():
            setattr(domain, key, value)
        await self.db.flush()
        return domain

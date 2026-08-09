from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agency import Agency
from app.models.approval import Approval, ApprovalToken
from app.models.asset import Asset
from app.models.branding import AgencyBrandingSettings
from app.models.brief import Brief
from app.models.plan import Plan
from app.models.report import Report, ReportShareToken
from app.models.subscription import Subscription
from app.repositories.asset import AssetRepository
from app.repositories.branding import (
    BrandingAssetRepository,
    BrandingSettingsRepository,
    CustomDomainRepository,
)
from app.schemas.branding import (
    BrandingSettingsRead,
    BrandingSettingsUpdate,
    CustomDomainCreated,
    CustomDomainRead,
    PublicBrandingView,
)
from app.services.platform_branding_service import PlatformBrandingService
from app.services.storage_service import get_storage_backend

_BRANDING_MIME_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
_MAX_BRANDING_ASSET_BYTES = 5 * 1024 * 1024  # 5 MB


def _asset_url(asset_id: uuid.UUID | None) -> str | None:
    if asset_id is None:
        return None
    return f"/api/v1/public/branding/assets/{asset_id}"


def _to_settings_read(settings: AgencyBrandingSettings, entitlement: bool) -> BrandingSettingsRead:
    return BrandingSettingsRead(
        id=settings.id,
        agency_id=settings.agency_id,
        brand_name_override=settings.brand_name_override,
        primary_color=settings.primary_color,
        secondary_color=settings.secondary_color,
        accent_color=settings.accent_color,
        logo_url=_asset_url(settings.logo_asset_id),
        email_logo_url=_asset_url(settings.email_logo_asset_id),
        favicon_url=_asset_url(settings.favicon_asset_id),
        custom_footer_text=settings.custom_footer_text,
        is_white_label_enabled=settings.is_white_label_enabled,
        white_label_entitlement=entitlement,
        created_at=settings.created_at,
        updated_at=settings.updated_at,
    )


async def _check_entitlement(db: AsyncSession, agency_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(Plan)
        .join(Subscription, Subscription.plan_id == Plan.id)
        .where(
            Subscription.agency_id == agency_id,
            Subscription.deleted_at.is_(None),
        )
    )
    plan = result.scalar_one_or_none()
    return plan is not None and plan.white_label_enabled


class BrandingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._settings_repo = BrandingSettingsRepository(db)
        self._asset_repo = BrandingAssetRepository(db)
        self._domain_repo = CustomDomainRepository(db)

    async def get_settings(self, agency_id: uuid.UUID) -> BrandingSettingsRead:
        settings = await self._settings_repo.get_by_agency(agency_id)
        entitlement = await _check_entitlement(self.db, agency_id)
        if settings is None:
            settings = await self._settings_repo.create(agency_id)
            await self.db.commit()
        return _to_settings_read(settings, entitlement)

    async def update_settings(
        self, agency_id: uuid.UUID, data: BrandingSettingsUpdate
    ) -> BrandingSettingsRead:
        entitlement = await _check_entitlement(self.db, agency_id)
        update_data = data.model_dump(exclude_none=True)

        if update_data.get("is_white_label_enabled") and not entitlement:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="White-label is not included in your current plan.",
            )

        settings = await self._settings_repo.get_by_agency(agency_id)
        if settings is None:
            settings = await self._settings_repo.create(agency_id)

        await self._settings_repo.update(settings, update_data)
        await self.db.commit()
        await self.db.refresh(settings)
        return _to_settings_read(settings, entitlement)

    async def upload_branding_asset(
        self,
        agency_id: uuid.UUID,
        uploaded_by_id: uuid.UUID,
        file: UploadFile,
        asset_type: str,
    ) -> BrandingSettingsRead:
        if file.content_type not in _BRANDING_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Unsupported file type '{file.content_type}'. "
                    "Allowed: PNG, JPEG, WebP, GIF."
                ),
            )

        data = await file.read()
        if len(data) > _MAX_BRANDING_ASSET_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Branding asset must be under 5 MB.",
            )

        ext = (file.filename or "image").rsplit(".", 1)[-1].lower()
        filename = f"{uuid.uuid4()}.{ext}"
        storage_key = f"{agency_id}/branding/{asset_type}/{filename}"

        storage = get_storage_backend()
        await storage.save(data, storage_key)

        asset_repo = AssetRepository(self.db)
        asset = await asset_repo.create(
            {
                "agency_id": agency_id,
                "uploaded_by_id": uploaded_by_id,
                "filename": filename,
                "original_filename": file.filename or filename,
                "mime_type": file.content_type,
                "size_bytes": len(data),
                "storage_provider": "local",
                "storage_key": storage_key,
            }
        )

        await self._asset_repo.create(agency_id, asset.id, asset_type)

        settings = await self._settings_repo.get_by_agency(agency_id)
        if settings is None:
            settings = await self._settings_repo.create(agency_id)

        field_map = {
            "logo": "logo_asset_id",
            "email_logo": "email_logo_asset_id",
            "favicon": "favicon_asset_id",
        }
        if asset_type in field_map:
            await self._settings_repo.update(settings, {field_map[asset_type]: asset.id})

        entitlement = await _check_entitlement(self.db, agency_id)
        await self.db.commit()
        await self.db.refresh(settings)
        return _to_settings_read(settings, entitlement)

    async def reset_settings(self, agency_id: uuid.UUID) -> BrandingSettingsRead:
        settings = await self._settings_repo.get_by_agency(agency_id)
        if settings is None:
            settings = await self._settings_repo.create(agency_id)
        else:
            await self._settings_repo.reset(settings)
        entitlement = await _check_entitlement(self.db, agency_id)
        await self.db.commit()
        await self.db.refresh(settings)
        return _to_settings_read(settings, entitlement)

    async def get_public_asset(self, asset_id: uuid.UUID) -> Asset:
        is_branding = await self._asset_repo.is_branding_asset(asset_id)
        if not is_branding:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
        result = await self.db.execute(
            select(Asset).where(Asset.id == asset_id, Asset.deleted_at.is_(None))
        )
        asset = result.scalar_one_or_none()
        if asset is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
        return asset

    async def get_public_branding_by_approval_token(self, raw_token: str) -> PublicBrandingView:
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        result = await self.db.execute(
            select(ApprovalToken).where(
                ApprovalToken.token_hash == token_hash,
                ApprovalToken.deleted_at.is_(None),
            )
        )
        approval_token = result.scalar_one_or_none()
        if approval_token is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid token.")

        result = await self.db.execute(
            select(Approval).where(Approval.id == approval_token.approval_id)
        )
        approval = result.scalar_one_or_none()
        if approval is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found.")

        result = await self.db.execute(select(Brief).where(Brief.id == approval.brief_id))
        brief = result.scalar_one_or_none()
        if brief is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brief not found.")

        return await self._build_public_branding(brief.agency_id)

    async def get_public_branding_by_report_token(self, raw_token: str) -> PublicBrandingView:
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        result = await self.db.execute(
            select(ReportShareToken).where(
                ReportShareToken.token_hash == token_hash,
                ReportShareToken.deleted_at.is_(None),
            )
        )
        share_token = result.scalar_one_or_none()
        if share_token is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid token.")

        now = datetime.now(UTC)
        if share_token.expires_at < now or share_token.revoked_at is not None:
            raise HTTPException(
                status_code=status.HTTP_410_GONE, detail="Token has expired or been revoked."
            )

        result = await self.db.execute(select(Report).where(Report.id == share_token.report_id))
        report = result.scalar_one_or_none()
        if report is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")

        return await self._build_public_branding(report.agency_id)

    async def _build_public_branding(self, agency_id: uuid.UUID) -> PublicBrandingView:
        result = await self.db.execute(
            select(Agency).where(Agency.id == agency_id, Agency.deleted_at.is_(None))
        )
        agency = result.scalar_one_or_none()
        agency_name = agency.name if agency else "Flobrief"

        settings = await self._settings_repo.get_by_agency(agency_id)
        entitlement = await _check_entitlement(self.db, agency_id)
        platform_defaults = await PlatformBrandingService(self.db).get_defaults()

        if settings is None or not settings.is_white_label_enabled or not entitlement:
            # No agency-level white-label — fall back to the platform's global
            # identity so the public portal never renders a bare/unbranded page.
            return PublicBrandingView(
                agency_name=agency_name,
                brand_name=platform_defaults.portal_name,
                primary_color=platform_defaults.primary_color,
                secondary_color=None,
                accent_color=platform_defaults.accent_color,
                logo_url=platform_defaults.logo_url,
                favicon_url=platform_defaults.favicon_url,
                custom_footer_text=platform_defaults.footer_text,
                is_branded=False,
            )

        # Agency has white-label enabled — use its own settings, falling back to
        # the platform default per-field wherever the agency left something unset.
        return PublicBrandingView(
            agency_name=agency_name,
            brand_name=settings.brand_name_override or platform_defaults.portal_name,
            primary_color=settings.primary_color or platform_defaults.primary_color,
            secondary_color=settings.secondary_color,
            accent_color=settings.accent_color or platform_defaults.accent_color,
            logo_url=_asset_url(settings.logo_asset_id) or platform_defaults.logo_url,
            favicon_url=_asset_url(settings.favicon_asset_id) or platform_defaults.favicon_url,
            custom_footer_text=settings.custom_footer_text or platform_defaults.footer_text,
            is_branded=True,
        )

    async def create_custom_domain(self, agency_id: uuid.UUID, domain: str) -> CustomDomainCreated:
        existing = await self._domain_repo.get_by_agency(agency_id)
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        if existing is not None:
            domain_obj = await self._domain_repo.update(
                existing,
                {
                    "domain": domain,
                    "status": "pending",
                    "verification_token_hash": token_hash,
                    "verified_at": None,
                },
            )
        else:
            domain_obj = await self._domain_repo.create(agency_id, domain, token_hash)

        await self.db.commit()
        await self.db.refresh(domain_obj)
        return CustomDomainCreated(
            id=domain_obj.id,
            agency_id=domain_obj.agency_id,
            domain=domain_obj.domain,
            status=domain_obj.status,
            verified_at=domain_obj.verified_at,
            created_at=domain_obj.created_at,
            updated_at=domain_obj.updated_at,
            verification_token=raw_token,
        )

    async def get_custom_domain(self, agency_id: uuid.UUID) -> CustomDomainRead:
        domain_obj = await self._domain_repo.get_by_agency(agency_id)
        if domain_obj is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No custom domain configured.",
            )
        return CustomDomainRead.model_validate(domain_obj)

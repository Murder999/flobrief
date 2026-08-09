"""Platform-level white-label defaults: global fallback identity for agencies
that have not enabled or fully configured their own branding."""

from __future__ import annotations

import contextlib
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_branding_defaults import PlatformBrandingDefaults
from app.schemas.platform_branding import (
    PlatformBrandingDefaultsRead,
    PlatformBrandingDefaultsUpdate,
)
from app.services.storage_service import get_storage_backend

_LOGO_MIME_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
_FAVICON_MIME_TYPES = {"image/png", "image/x-icon", "image/vnd.microsoft.icon"}
_MAX_ASSET_BYTES = 5 * 1024 * 1024  # 5 MB

_ASSET_TYPES = {"logo", "logo_dark", "favicon"}

_ASSET_URL_MAP = {
    "logo": "/api/v1/public/branding/platform-logo",
    "logo_dark": "/api/v1/public/branding/platform-logo-dark",
    "favicon": "/api/v1/public/branding/platform-favicon",
}


def _asset_url(field_value: str | None, asset_type: str) -> str | None:
    return _ASSET_URL_MAP[asset_type] if field_value else None


def _to_read(defaults: PlatformBrandingDefaults) -> PlatformBrandingDefaultsRead:
    return PlatformBrandingDefaultsRead(
        portal_name=defaults.portal_name,
        login_title=defaults.login_title,
        login_description=defaults.login_description,
        primary_color=defaults.primary_color,
        accent_color=defaults.accent_color,
        background_color=defaults.background_color,
        surface_color=defaults.surface_color,
        text_color=defaults.text_color,
        link_color=defaults.link_color,
        logo_url=_asset_url(defaults.logo_storage_key, "logo"),
        logo_dark_url=_asset_url(defaults.logo_dark_storage_key, "logo_dark"),
        favicon_url=_asset_url(defaults.favicon_storage_key, "favicon"),
        email_from_name=defaults.email_from_name,
        support_email=defaults.support_email,
        footer_text=defaults.footer_text,
        terms_url=defaults.terms_url,
        privacy_url=defaults.privacy_url,
        social_links=defaults.social_links,
        updated_at=defaults.updated_at,
    )


class PlatformBrandingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _get_or_create(self) -> PlatformBrandingDefaults:
        result = await self.db.execute(
            select(PlatformBrandingDefaults).where(
                PlatformBrandingDefaults.setting_key == "default",
                PlatformBrandingDefaults.deleted_at.is_(None),
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = PlatformBrandingDefaults(setting_key="default")
            self.db.add(row)
            await self.db.flush()
        return row

    async def get_defaults(self) -> PlatformBrandingDefaultsRead:
        row = await self._get_or_create()
        await self.db.commit()
        return _to_read(row)

    async def update_defaults(
        self, data: PlatformBrandingDefaultsUpdate
    ) -> PlatformBrandingDefaultsRead:
        row = await self._get_or_create()
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(row, key, value)
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return _to_read(row)

    async def reset_defaults(self) -> PlatformBrandingDefaultsRead:
        row = await self._get_or_create()
        for field in (
            "portal_name",
            "login_title",
            "login_description",
            "primary_color",
            "accent_color",
            "background_color",
            "surface_color",
            "text_color",
            "link_color",
            "logo_storage_key",
            "logo_mime_type",
            "logo_dark_storage_key",
            "logo_dark_mime_type",
            "favicon_storage_key",
            "favicon_mime_type",
            "email_from_name",
            "support_email",
            "footer_text",
            "terms_url",
            "privacy_url",
            "social_links",
        ):
            setattr(row, field, None)
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return _to_read(row)

    async def upload_asset(self, file: UploadFile, asset_type: str) -> PlatformBrandingDefaultsRead:
        if asset_type not in _ASSET_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"asset_type must be one of: {', '.join(sorted(_ASSET_TYPES))}",
            )
        allowed = _FAVICON_MIME_TYPES if asset_type == "favicon" else _LOGO_MIME_TYPES
        if file.content_type not in allowed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unsupported file type '{file.content_type}' for {asset_type}.",
            )

        data = await file.read()
        if not data:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Uploaded file is empty or corrupted.",
            )
        if len(data) > _MAX_ASSET_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Branding asset must be under 5 MB.",
            )

        ext = (file.filename or "image").rsplit(".", 1)[-1].lower()
        filename = f"{uuid.uuid4()}.{ext}"
        storage_key = f"platform/branding/{asset_type}/{filename}"

        storage = get_storage_backend()
        await storage.save(data, storage_key)

        row = await self._get_or_create()
        old_key = getattr(row, f"{asset_type}_storage_key")
        setattr(row, f"{asset_type}_storage_key", storage_key)
        setattr(row, f"{asset_type}_mime_type", file.content_type)
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)

        if old_key:
            with contextlib.suppress(OSError):
                # best-effort cleanup; stale files don't affect correctness
                await storage.delete(old_key)

        return _to_read(row)

    async def get_asset_file(self, asset_type: str) -> tuple[str, str]:
        """Returns (absolute_path, mime_type) for a configured platform asset, or 404."""
        if asset_type not in _ASSET_TYPES:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
        row = await self._get_or_create()
        await self.db.commit()
        storage_key = getattr(row, f"{asset_type}_storage_key")
        mime_type = getattr(row, f"{asset_type}_mime_type")
        if not storage_key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not configured.")
        storage = get_storage_backend()
        return storage.get_path(storage_key), mime_type or "application/octet-stream"

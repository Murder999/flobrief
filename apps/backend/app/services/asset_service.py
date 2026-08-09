from __future__ import annotations

import hashlib
import logging
import uuid as uuid_mod

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext
from app.core.config import settings
from app.models.asset import Asset
from app.models.brief import Brief
from app.repositories.asset import (
    AssetLinkRepository,
    AssetRepository,
    AssetVersionRepository,
)
from app.schemas.asset import AssetLinkRead, AssetRead, AssetVersionRead
from app.services.media_metadata import extract_image_dimensions
from app.services.storage_service import (
    get_storage_backend,
    normalize_filename,
    validate_file_size,
    validate_mime_type,
)

logger = logging.getLogger(__name__)

_BRAND_REFERENCE_UPLOAD_STATUSES = frozenset(
    {
        "draft",
        "submitted",
        "revision_requested",
    }
)


class AssetService:
    def __init__(self, db: AsyncSession, workspace: WorkspaceContext) -> None:
        self.db = db
        self.workspace = workspace
        self.asset_repo = AssetRepository(db)
        self.version_repo = AssetVersionRepository(db)
        self.link_repo = AssetLinkRepository(db)
        self._storage = get_storage_backend()

    async def _require_brief(self, brief_id: uuid_mod.UUID) -> Brief:
        result = await self.db.execute(
            select(Brief).where(
                Brief.id == brief_id,
                Brief.agency_id == self.workspace.agency.id,
                Brief.deleted_at.is_(None),
            )
        )
        brief = result.scalar_one_or_none()
        if not brief:
            raise HTTPException(status_code=404, detail="Brief not found")
        return brief

    async def _require_asset(self, asset_id: uuid_mod.UUID) -> Asset:
        asset = await self.asset_repo.get_by_id(asset_id, self.workspace.agency.id)
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        return asset

    async def upload(
        self,
        brief_id: uuid_mod.UUID,
        file: UploadFile,
    ) -> AssetRead:
        brief = await self._require_brief(brief_id)

        data = await file.read()
        mime = file.content_type or "application/octet-stream"
        validate_mime_type(mime)
        validate_file_size(len(data))

        checksum = hashlib.sha256(data).hexdigest()
        original_name = file.filename or "upload"
        safe_name = normalize_filename(original_name)
        storage_key = f"{self.workspace.agency.id}/{safe_name}"

        await self._storage.save(data, storage_key)

        dimensions = extract_image_dimensions(data, mime)

        asset = await self.asset_repo.create(
            {
                "agency_id": self.workspace.agency.id,
                "uploaded_by_id": self.workspace.user.id,
                "filename": safe_name,
                "original_filename": original_name[:500],
                "mime_type": mime,
                "size_bytes": len(data),
                "storage_provider": "local",
                "storage_key": storage_key,
                "checksum": checksum,
                "width_px": dimensions[0] if dimensions else None,
                "height_px": dimensions[1] if dimensions else None,
            }
        )

        await self.link_repo.create(
            {
                "asset_id": asset.id,
                "brief_id": brief_id,
            }
        )

        from app.models.enums import NotificationEventType
        from app.services.notification_dispatcher import NotificationDispatcher

        await NotificationDispatcher(self.db).emit(
            NotificationEventType.FILE_UPLOADED.value,
            payload={
                "brief_id": str(brief_id),
                "brief_title": brief.title,
                "file_name": original_name,
                "summary": f"Dosya yüklendi: {original_name}",
            },
            agency_id=self.workspace.agency.id,
            brand_id=brief.brand_id,
            actor_user_id=self.workspace.user.id,
        )

        await self.db.commit()
        await self.db.refresh(asset)
        return AssetRead.model_validate(asset)

    async def list_for_brief(self, brief_id: uuid_mod.UUID) -> list[AssetRead]:
        await self._require_brief(brief_id)
        assets = await self.asset_repo.list_for_brief(brief_id, self.workspace.agency.id)
        return [AssetRead.model_validate(a) for a in assets]

    async def upload_brand_reference(
        self,
        brief_id: uuid_mod.UUID,
        brand_id: uuid_mod.UUID,
        file: UploadFile,
    ) -> AssetRead:
        """Upload a brand-owned reference file to a brand-owned brief."""
        brief = await self._require_brief(brief_id)
        if brief.brand_id != brand_id:
            raise HTTPException(status_code=404, detail="Brief bulunamadı")
        if brief.status not in _BRAND_REFERENCE_UPLOAD_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Yalnızca taslak, gönderilmiş veya revizyon " "brief'lerine dosya yüklenebilir"
                ),
            )

        data = await file.read()
        mime = file.content_type or "application/octet-stream"
        validate_mime_type(mime)
        validate_file_size(len(data))

        original_name = file.filename or "upload"
        safe_name = normalize_filename(original_name)
        storage_key = f"{self.workspace.agency.id}/brand-references/{brand_id}/{safe_name}"
        await self._storage.save(data, storage_key)

        try:
            dimensions = extract_image_dimensions(data, mime)
            asset = await self.asset_repo.create(
                {
                    "agency_id": self.workspace.agency.id,
                    "brand_id": brand_id,
                    "uploaded_by_id": self.workspace.user.id,
                    "filename": safe_name,
                    "original_filename": original_name[:500],
                    "mime_type": mime,
                    "size_bytes": len(data),
                    "storage_provider": settings.STORAGE_BACKEND.lower(),
                    "storage_key": storage_key,
                    "checksum": hashlib.sha256(data).hexdigest(),
                    "visibility": "brand_reference",
                    "width_px": dimensions[0] if dimensions else None,
                    "height_px": dimensions[1] if dimensions else None,
                }
            )
            await self.link_repo.create(
                {
                    "asset_id": asset.id,
                    "brief_id": brief_id,
                }
            )

            from app.models.enums import NotificationEventType
            from app.services.notification_dispatcher import NotificationDispatcher

            await NotificationDispatcher(self.db).emit(
                NotificationEventType.FILE_UPLOADED.value,
                payload={
                    "brief_id": str(brief_id),
                    "brief_title": brief.title,
                    "file_name": original_name,
                    "summary": f"Marka referans dosyası yükledi: {original_name}",
                },
                agency_id=self.workspace.agency.id,
                brand_id=brand_id,
                actor_user_id=self.workspace.user.id,
            )
            await self.db.commit()
            await self.db.refresh(asset)
            return AssetRead.model_validate(asset)
        except Exception:
            await self.db.rollback()
            try:
                await self._storage.delete(storage_key)
            except Exception:
                logger.exception(
                    "Failed to clean up brand reference storage object %s",
                    storage_key,
                )
            raise

    async def list_for_brand_brief(
        self,
        brief_id: uuid_mod.UUID,
        brand_id: uuid_mod.UUID,
    ) -> list[AssetRead]:
        brief = await self._require_brief(brief_id)
        if brief.brand_id != brand_id:
            raise HTTPException(status_code=404, detail="Brief bulunamadı")
        assets = await self.asset_repo.list_for_brand_brief(
            brief_id,
            self.workspace.agency.id,
        )
        return [AssetRead.model_validate(asset) for asset in assets]

    async def get(self, asset_id: uuid_mod.UUID) -> AssetRead:
        asset = await self._require_asset(asset_id)
        return AssetRead.model_validate(asset)

    async def delete(self, asset_id: uuid_mod.UUID) -> None:
        asset = await self._require_asset(asset_id)
        asset.soft_delete()
        await self.db.commit()

    async def delete_brand_reference(
        self,
        asset_id: uuid_mod.UUID,
        brand_id: uuid_mod.UUID,
    ) -> None:
        asset = await self._require_asset(asset_id)
        if asset.brand_id != brand_id or asset.visibility != "brand_reference":
            raise HTTPException(status_code=404, detail="Asset not found")
        asset.soft_delete()
        await self.db.commit()

    async def get_download_info(self, asset_id: uuid_mod.UUID) -> tuple[str, AssetRead]:
        asset = await self._require_asset(asset_id)
        path = self._storage.get_path(asset.storage_key)
        return path, AssetRead.model_validate(asset)

    async def create_version(self, asset_id: uuid_mod.UUID, file: UploadFile) -> AssetVersionRead:
        await self._require_asset(asset_id)

        data = await file.read()
        mime = file.content_type or "application/octet-stream"
        validate_mime_type(mime)
        validate_file_size(len(data))

        checksum = hashlib.sha256(data).hexdigest()
        safe_name = normalize_filename(file.filename or "upload")
        storage_key = f"{self.workspace.agency.id}/versions/{asset_id}/{safe_name}"

        await self._storage.save(data, storage_key)

        dimensions = extract_image_dimensions(data, mime)

        version_number = await self.version_repo.next_version_number(asset_id)
        version = await self.version_repo.create(
            {
                "asset_id": asset_id,
                "version_number": version_number,
                "storage_key": storage_key,
                "filename": safe_name,
                "mime_type": mime,
                "size_bytes": len(data),
                "checksum": checksum,
                "uploaded_by_id": self.workspace.user.id,
                "width_px": dimensions[0] if dimensions else None,
                "height_px": dimensions[1] if dimensions else None,
            }
        )

        await self.db.commit()
        await self.db.refresh(version)
        return AssetVersionRead.model_validate(version)

    async def link_to_brief(
        self,
        asset_id: uuid_mod.UUID,
        brief_id: uuid_mod.UUID,
    ) -> AssetLinkRead:
        await self._require_asset(asset_id)
        await self._require_brief(brief_id)

        link = await self.link_repo.create(
            {
                "asset_id": asset_id,
                "brief_id": brief_id,
            }
        )
        await self.db.commit()
        await self.db.refresh(link)
        return AssetLinkRead.model_validate(link)

    async def unlink(self, link_id: uuid_mod.UUID) -> None:
        link = await self.link_repo.get_by_id(link_id)
        if not link:
            raise HTTPException(status_code=404, detail="Link not found")

        asset = await self.asset_repo.get_by_id(link.asset_id, self.workspace.agency.id)
        if not asset:
            raise HTTPException(status_code=403, detail="Access denied")

        await self.link_repo.hard_delete(link)
        await self.db.commit()

from __future__ import annotations

import io
import uuid

import pytest
from PIL import Image

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.asset import Asset, AssetLink
from app.models.brief import Brief


def _brand_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _one_pixel_png() -> io.BytesIO:
    content = io.BytesIO()
    Image.new("RGBA", (1, 1), (255, 255, 255, 255)).save(content, format="PNG")
    content.seek(0)
    return content


@pytest.mark.asyncio
async def test_brand_asset_route_uploads_lists_once_and_hides_internal_assets(
    client,
    tenants,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant, _ = tenants
    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path))

    uploaded = await client.post(
        f"/api/v1/brand-portal/briefs/{tenant.brief_id}/assets",
        headers=_brand_headers(tenant.brand_manager_token),
        files={"file": ("reference.png", _one_pixel_png(), "image/png")},
    )
    assert uploaded.status_code == 201, uploaded.text
    uploaded_id = uuid.UUID(uploaded.json()["id"])

    async with AsyncSessionLocal() as session:
        asset = await session.get(Asset, uploaded_id)
        assert asset is not None
        assert asset.brand_id == tenant.brand_id
        assert asset.visibility == "brand_reference"
        assert asset.width_px == 1
        assert asset.height_px == 1

        session.add(AssetLink(asset_id=uploaded_id, brief_id=tenant.brief_id))
        internal = Asset(
            agency_id=tenant.agency_id,
            brand_id=tenant.brand_id,
            uploaded_by_id=tenant.agency_user_id,
            filename="internal.txt",
            original_filename="internal.txt",
            mime_type="text/plain",
            size_bytes=6,
            storage_provider="local",
            storage_key=f"{tenant.agency_id}/internal/{uuid.uuid4()}.txt",
            visibility="internal",
        )
        session.add(internal)
        await session.flush()
        session.add(AssetLink(asset_id=internal.id, brief_id=tenant.brief_id))
        await session.commit()

    listed = await client.get(
        f"/api/v1/brand-portal/briefs/{tenant.brief_id}/assets",
        headers=_brand_headers(tenant.brand_manager_token),
    )
    assert listed.status_code == 200
    listed_ids = [item["id"] for item in listed.json()]
    assert listed_ids == [str(uploaded_id)]


@pytest.mark.asyncio
async def test_brand_cannot_delete_another_brands_reference_in_same_agency(
    client,
    tenants,
) -> None:
    tenant, other_tenant = tenants
    async with AsyncSessionLocal() as session:
        foreign_asset = Asset(
            agency_id=tenant.agency_id,
            brand_id=other_tenant.brand_id,
            uploaded_by_id=tenant.agency_user_id,
            filename="foreign.pdf",
            original_filename="foreign.pdf",
            mime_type="application/pdf",
            size_bytes=10,
            storage_provider="local",
            storage_key=f"{tenant.agency_id}/foreign/{uuid.uuid4()}.pdf",
            visibility="brand_reference",
        )
        session.add(foreign_asset)
        await session.commit()
        foreign_asset_id = foreign_asset.id

    response = await client.delete(
        f"/api/v1/brand-portal/assets/{foreign_asset_id}",
        headers=_brand_headers(tenant.brand_manager_token),
    )
    assert response.status_code == 404

    async with AsyncSessionLocal() as session:
        asset = await session.get(Asset, foreign_asset_id)
        assert asset is not None
        assert asset.deleted_at is None


@pytest.mark.asyncio
async def test_brand_reference_upload_rejects_closed_brief(
    client,
    tenants,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant, _ = tenants
    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path))
    async with AsyncSessionLocal() as session:
        brief = await session.get(Brief, tenant.brief_id)
        assert brief is not None
        brief.status = "completed"
        await session.commit()

    response = await client.post(
        f"/api/v1/brand-portal/briefs/{tenant.brief_id}/assets",
        headers=_brand_headers(tenant.brand_manager_token),
        files={"file": ("late.png", _one_pixel_png(), "image/png")},
    )
    assert response.status_code == 400

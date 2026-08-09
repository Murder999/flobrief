"""Tests for app.services.media_metadata.extract_image_dimensions and its wiring
into every asset-creation call site (AssetService.upload/create_version,
deliverables.upload_deliverable_asset).

All image bytes used here are real, Pillow-encoded PNGs (via PIL.Image.new +
.save()) — Pillow genuinely decodes them and returns their true width/height,
so this exercises the real extraction path rather than asserting a fabricated
number.
"""

from __future__ import annotations

import io
import uuid

from httpx import AsyncClient
from PIL import Image

from app.db.session import AsyncSessionLocal
from app.models.asset import Asset
from app.services.media_metadata import extract_image_dimensions
from app.tests.conftest import agency_headers


def _png_bytes(width: int, height: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


# ── Pure function ─────────────────────────────────────────────────────────────


class TestExtractImageDimensions:
    def test_real_png_returns_correct_dimensions(self) -> None:
        data = _png_bytes(640, 480)
        result = extract_image_dimensions(data, "image/png")
        assert result == (640, 480)

    def test_real_jpeg_returns_correct_dimensions(self) -> None:
        buf = io.BytesIO()
        Image.new("RGB", (1080, 1350), color=(1, 2, 3)).save(buf, format="JPEG")
        result = extract_image_dimensions(buf.getvalue(), "image/jpeg")
        assert result == (1080, 1350)

    def test_non_image_mime_returns_none(self) -> None:
        result = extract_image_dimensions(b"%PDF-1.4 fake pdf body", "application/pdf")
        assert result is None

    def test_corrupt_image_bytes_return_none_without_raising(self) -> None:
        result = extract_image_dimensions(b"not a real image at all", "image/png")
        assert result is None

    def test_empty_bytes_return_none(self) -> None:
        result = extract_image_dimensions(b"", "image/png")
        assert result is None

    def test_truncated_png_returns_none(self) -> None:
        data = _png_bytes(200, 200)[:20]  # truncate mid-header
        result = extract_image_dimensions(data, "image/png")
        assert result is None


# ── Wiring into upload call sites (live DB + real app) ───────────────────────


class TestAssetUploadCapturesDimensions:
    async def test_general_asset_upload_captures_dimensions(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, _ = tenants
        data = _png_bytes(800, 600)
        resp = await client.post(
            f"/api/v1/briefs/{tenant_a.brief_id}/assets",
            headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
            files={"file": ("photo.png", io.BytesIO(data), "image/png")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["width_px"] == 800
        assert body["height_px"] == 600

    async def test_deliverable_asset_upload_captures_dimensions(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, _ = tenants
        headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        create_resp = await client.post(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables",
            headers=headers,
            json={"title": "Preview Deliverable", "deliverable_type": "image"},
        )
        assert create_resp.status_code == 201
        deliverable_id = create_resp.json()["id"]

        data = _png_bytes(1080, 1080)
        resp = await client.post(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/assets",
            headers=headers,
            files={"file": ("square.png", io.BytesIO(data), "image/png")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["width_px"] == 1080
        assert body["height_px"] == 1080

    async def test_non_image_upload_leaves_dimensions_null(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, _ = tenants
        resp = await client.post(
            f"/api/v1/briefs/{tenant_a.brief_id}/assets",
            headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
            files={"file": ("doc.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["width_px"] is None
        assert body["height_px"] is None

    async def test_asset_version_upload_captures_dimensions(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, _ = tenants
        headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        upload_resp = await client.post(
            f"/api/v1/briefs/{tenant_a.brief_id}/assets",
            headers=headers,
            files={"file": ("v1.png", io.BytesIO(_png_bytes(300, 200)), "image/png")},
        )
        asset_id = upload_resp.json()["id"]

        version_resp = await client.post(
            f"/api/v1/assets/{asset_id}/versions",
            headers=headers,
            files={"file": ("v2.png", io.BytesIO(_png_bytes(500, 400)), "image/png")},
        )
        assert version_resp.status_code == 201
        body = version_resp.json()
        assert body["width_px"] == 500
        assert body["height_px"] == 400

    async def test_asset_row_persisted_with_dimensions(self, client: AsyncClient, tenants) -> None:
        """Confirms the columns are actually persisted to Postgres, not just
        echoed back in the response body."""
        tenant_a, _ = tenants
        resp = await client.post(
            f"/api/v1/briefs/{tenant_a.brief_id}/assets",
            headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
            files={"file": ("p.png", io.BytesIO(_png_bytes(222, 111)), "image/png")},
        )
        asset_id = uuid.UUID(resp.json()["id"])

        async with AsyncSessionLocal() as session:
            asset = await session.get(Asset, asset_id)
            assert asset is not None
            assert asset.width_px == 222
            assert asset.height_px == 111

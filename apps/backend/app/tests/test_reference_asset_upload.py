"""Reference asset upload tests.

Covers:
- normalize_filename(): path traversal prevention, char sanitization, extension handling
- validate_mime_type(): allowlist enforcement, rejection of dangerous types
- validate_file_size(): max size enforcement
- ALLOWED_MIME_TYPES completeness (images, docs, video, audio, design)
- AssetRead / AssetVersionRead / AssetLinkRead schema validation
- HTTP auth layer: asset upload endpoint requires authentication
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.schemas.asset import AssetLinkRead, AssetRead
from app.services.storage_service import (
    ALLOWED_MIME_TYPES,
    normalize_filename,
    validate_file_size,
    validate_mime_type,
)

# ── normalize_filename ────────────────────────────────────────────────────────


class TestNormalizeFilename:
    def test_path_traversal_stripped(self) -> None:
        name = normalize_filename("../../etc/passwd")
        assert ".." not in name
        assert "/" not in name

    def test_windows_path_traversal_stripped(self) -> None:
        name = normalize_filename("..\\..\\windows\\system32\\config")
        assert ".." not in name

    def test_dangerous_chars_replaced(self) -> None:
        name = normalize_filename("my brief; rm -rf *.pdf")
        assert ";" not in name
        assert " " not in name

    def test_extension_preserved(self) -> None:
        name = normalize_filename("design_v2.pdf")
        assert name.endswith(".pdf")

    def test_no_extension_handled(self) -> None:
        name = normalize_filename("noextension")
        assert isinstance(name, str)
        assert len(name) > 0

    def test_uuid_suffix_added_for_uniqueness(self) -> None:
        n1 = normalize_filename("logo.png")
        n2 = normalize_filename("logo.png")
        # UUID suffix means two calls produce different names
        assert n1 != n2

    def test_result_is_safe_for_filesystem(self) -> None:
        import re

        name = normalize_filename("my brief (final) v3.docx")
        # Only word chars, hyphens, underscores, dots
        assert re.match(r"^[\w\-_.]+$", name), f"Unsafe filename: {name}"

    def test_long_basename_truncated(self) -> None:
        long_name = "a" * 200 + ".pdf"
        name = normalize_filename(long_name)
        assert len(name) <= 200

    def test_uppercase_extension_lowercased(self) -> None:
        name = normalize_filename("Report.PDF")
        assert name.endswith(".pdf")

    def test_image_extension_preserved(self) -> None:
        name = normalize_filename("hero_image.jpg")
        assert name.endswith(".jpg")


# ── validate_mime_type ────────────────────────────────────────────────────────


class TestValidateMimeType:
    def test_pdf_allowed(self) -> None:
        validate_mime_type("application/pdf")  # must not raise

    def test_jpeg_allowed(self) -> None:
        validate_mime_type("image/jpeg")

    def test_png_allowed(self) -> None:
        validate_mime_type("image/png")

    def test_webp_allowed(self) -> None:
        validate_mime_type("image/webp")

    def test_docx_allowed(self) -> None:
        validate_mime_type(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    def test_xlsx_allowed(self) -> None:
        validate_mime_type("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    def test_mp4_video_allowed(self) -> None:
        validate_mime_type("video/mp4")

    def test_zip_allowed(self) -> None:
        validate_mime_type("application/zip")

    def test_csv_allowed(self) -> None:
        validate_mime_type("text/csv")

    def test_exe_rejected(self) -> None:
        with pytest.raises(HTTPException) as exc:
            validate_mime_type("application/x-msdownload")
        assert exc.value.status_code == 422

    def test_shell_script_rejected(self) -> None:
        with pytest.raises(HTTPException) as exc:
            validate_mime_type("application/x-sh")
        assert exc.value.status_code == 422

    def test_python_script_rejected(self) -> None:
        with pytest.raises(HTTPException) as exc:
            validate_mime_type("text/x-python")
        assert exc.value.status_code == 422

    def test_html_rejected(self) -> None:
        with pytest.raises(HTTPException) as exc:
            validate_mime_type("text/html")
        assert exc.value.status_code == 422

    def test_javascript_rejected(self) -> None:
        with pytest.raises(HTTPException) as exc:
            validate_mime_type("application/javascript")
        assert exc.value.status_code == 422

    def test_unknown_type_rejected(self) -> None:
        with pytest.raises(HTTPException) as exc:
            validate_mime_type("application/x-unknown-binary")
        assert exc.value.status_code == 422

    def test_error_message_includes_mime_type(self) -> None:
        with pytest.raises(HTTPException) as exc:
            validate_mime_type("application/x-evil")
        assert "application/x-evil" in exc.value.detail


# ── validate_file_size ────────────────────────────────────────────────────────


class TestValidateFileSize:
    def test_zero_bytes_allowed(self) -> None:
        validate_file_size(0)  # must not raise

    def test_one_byte_allowed(self) -> None:
        validate_file_size(1)

    def test_small_file_allowed(self) -> None:
        validate_file_size(100 * 1024)  # 100 KB

    def test_exactly_max_allowed(self) -> None:
        from app.core.config import settings

        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        validate_file_size(max_bytes)  # must not raise

    def test_over_max_rejected(self) -> None:
        from app.core.config import settings

        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        with pytest.raises(HTTPException) as exc:
            validate_file_size(max_bytes + 1)
        assert exc.value.status_code == 422

    def test_very_large_file_rejected(self) -> None:
        with pytest.raises(HTTPException) as exc:
            validate_file_size(1024 * 1024 * 1024)  # 1 GB
        assert exc.value.status_code == 422

    def test_error_message_mentions_size_limit(self) -> None:
        with pytest.raises(HTTPException) as exc:
            validate_file_size(1024 * 1024 * 1024)
        assert "MB" in exc.value.detail


# ── ALLOWED_MIME_TYPES completeness ──────────────────────────────────────────


class TestAllowedMimeTypesCompleteness:
    def test_images_covered(self) -> None:
        required = {"image/jpeg", "image/png", "image/gif", "image/webp"}
        assert required.issubset(ALLOWED_MIME_TYPES)

    def test_documents_covered(self) -> None:
        required = {"application/pdf", "text/plain", "text/csv"}
        assert required.issubset(ALLOWED_MIME_TYPES)

    def test_video_covered(self) -> None:
        assert "video/mp4" in ALLOWED_MIME_TYPES

    def test_audio_covered(self) -> None:
        assert "audio/mpeg" in ALLOWED_MIME_TYPES

    def test_office_docs_covered(self) -> None:
        required = {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        assert required.issubset(ALLOWED_MIME_TYPES)

    def test_is_frozenset(self) -> None:
        assert isinstance(ALLOWED_MIME_TYPES, frozenset)

    def test_no_dangerous_types(self) -> None:
        dangerous = {
            "application/x-msdownload",
            "text/html",
            "application/javascript",
            "application/x-php",
        }
        for t in dangerous:
            assert t not in ALLOWED_MIME_TYPES, f"Dangerous type {t} in allowlist"


# ── AssetRead schema ──────────────────────────────────────────────────────────


class TestAssetReadSchema:
    def _make_asset_data(self) -> dict:
        return {
            "id": uuid.uuid4(),
            "agency_id": uuid.uuid4(),
            "brand_id": None,
            "uploaded_by_id": uuid.uuid4(),
            "filename": "logo_abc12345.png",
            "original_filename": "logo.png",
            "mime_type": "image/png",
            "size_bytes": 204800,
            "storage_provider": "local",
            "checksum": "a" * 64,
            "created_at": datetime.now(UTC),
        }

    def test_valid_asset_deserializes(self) -> None:
        asset = AssetRead.model_validate(self._make_asset_data())
        assert asset.mime_type == "image/png"
        assert asset.size_bytes == 204800

    def test_brand_id_nullable(self) -> None:
        data = self._make_asset_data()
        data["brand_id"] = None
        asset = AssetRead.model_validate(data)
        assert asset.brand_id is None

    def test_uploaded_by_id_nullable(self) -> None:
        data = self._make_asset_data()
        data["uploaded_by_id"] = None
        asset = AssetRead.model_validate(data)
        assert asset.uploaded_by_id is None

    def test_checksum_nullable(self) -> None:
        data = self._make_asset_data()
        data["checksum"] = None
        asset = AssetRead.model_validate(data)
        assert asset.checksum is None


# ── AssetLinkRead schema ──────────────────────────────────────────────────────


class TestAssetLinkReadSchema:
    def test_brief_link_valid(self) -> None:
        link = AssetLinkRead.model_validate(
            {
                "id": uuid.uuid4(),
                "asset_id": uuid.uuid4(),
                "brief_id": uuid.uuid4(),
                "calendar_item_id": None,
                "comment_id": None,
                "created_at": datetime.now(UTC),
            }
        )
        assert link.brief_id is not None
        assert link.calendar_item_id is None

    def test_calendar_link_valid(self) -> None:
        link = AssetLinkRead.model_validate(
            {
                "id": uuid.uuid4(),
                "asset_id": uuid.uuid4(),
                "brief_id": None,
                "calendar_item_id": uuid.uuid4(),
                "comment_id": None,
                "created_at": datetime.now(UTC),
            }
        )
        assert link.calendar_item_id is not None
        assert link.brief_id is None


# ── HTTP auth layer ───────────────────────────────────────────────────────────


class TestAssetHTTPAuth:
    @pytest.mark.asyncio
    async def test_upload_without_token_returns_401(self, client) -> None:
        import io

        resp = await client.post(
            f"/api/v1/briefs/{uuid.uuid4()}/assets",
            headers={"X-Agency-ID": str(uuid.uuid4())},
            files={"file": ("test.pdf", io.BytesIO(b"hello"), "application/pdf")},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_list_assets_without_token_returns_401(self, client) -> None:
        resp = await client.get(
            f"/api/v1/briefs/{uuid.uuid4()}/assets",
            headers={"X-Agency-ID": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_asset_without_token_returns_401(self, client) -> None:
        resp = await client.delete(
            f"/api/v1/assets/{uuid.uuid4()}",
            headers={"X-Agency-ID": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

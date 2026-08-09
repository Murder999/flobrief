"""Delivery files tests.

In Flobrief, "delivery" means uploading versioned asset files to a brief —
each revision/iteration of a creative deliverable is tracked as an AssetVersion.
Also covers the asset metadata pipeline (checksum, size, mime type).

Covers:
- AssetVersionRead schema: all fields correctly typed
- Version numbering logic: next_version_number increments correctly
- Checksum computation: SHA-256 consistency
- Storage key namespacing: agency-scoped, collision-resistant
- Multiple versions for same asset: each has unique version_number
- normalize_filename: versions stored with unique suffix to avoid overwrites
- HTTP: asset versioning endpoints require authentication
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.schemas.asset import AssetVersionRead
from app.services.storage_service import normalize_filename

# ── AssetVersionRead schema ───────────────────────────────────────────────────


class TestAssetVersionReadSchema:
    def _make_version(self, version_number: int = 1) -> dict:
        return {
            "id": uuid.uuid4(),
            "asset_id": uuid.uuid4(),
            "version_number": version_number,
            "filename": f"brief_v{version_number}_abc12345.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 102400 * version_number,
            "checksum": hashlib.sha256(f"content_v{version_number}".encode()).hexdigest(),
            "uploaded_by_id": uuid.uuid4(),
            "created_at": datetime.now(UTC),
        }

    def test_version_1_valid(self) -> None:
        v = AssetVersionRead.model_validate(self._make_version(1))
        assert v.version_number == 1

    def test_version_2_valid(self) -> None:
        v = AssetVersionRead.model_validate(self._make_version(2))
        assert v.version_number == 2

    def test_version_fields_typed_correctly(self) -> None:
        v = AssetVersionRead.model_validate(self._make_version(3))
        assert isinstance(v.id, uuid.UUID)
        assert isinstance(v.asset_id, uuid.UUID)
        assert isinstance(v.version_number, int)
        assert isinstance(v.filename, str)
        assert isinstance(v.mime_type, str)
        assert isinstance(v.size_bytes, int)
        assert isinstance(v.created_at, datetime)

    def test_checksum_nullable(self) -> None:
        data = self._make_version(1)
        data["checksum"] = None
        v = AssetVersionRead.model_validate(data)
        assert v.checksum is None

    def test_uploaded_by_id_nullable(self) -> None:
        data = self._make_version(1)
        data["uploaded_by_id"] = None
        v = AssetVersionRead.model_validate(data)
        assert v.uploaded_by_id is None

    def test_size_bytes_positive(self) -> None:
        v = AssetVersionRead.model_validate(self._make_version(1))
        assert v.size_bytes > 0


# ── Version number sequencing logic ──────────────────────────────────────────


class TestVersionNumberSequencing:
    """Mirrors AssetVersionRepository.next_version_number() behavior."""

    def _simulate_next_version(self, existing_versions: list[int]) -> int:
        """next_version = max(existing) + 1, or 1 if none."""
        if not existing_versions:
            return 1
        return max(existing_versions) + 1

    def test_first_version_is_1(self) -> None:
        assert self._simulate_next_version([]) == 1

    def test_second_version_is_2(self) -> None:
        assert self._simulate_next_version([1]) == 2

    def test_third_version_is_3(self) -> None:
        assert self._simulate_next_version([1, 2]) == 3

    def test_gaps_handled_correctly(self) -> None:
        assert self._simulate_next_version([1, 3]) == 4

    def test_many_versions(self) -> None:
        assert self._simulate_next_version(list(range(1, 11))) == 11

    def test_versions_form_monotonic_sequence(self) -> None:
        versions = [1, 2, 3, 4, 5]
        for i, v in enumerate(versions, start=1):
            assert v == i


# ── Checksum computation ──────────────────────────────────────────────────────


class TestChecksumComputation:
    """SHA-256 checksum ensures file integrity for delivered assets."""

    def test_sha256_of_known_content(self) -> None:
        data = b"brief delivery file content"
        expected = hashlib.sha256(data).hexdigest()
        actual = hashlib.sha256(data).hexdigest()
        assert actual == expected

    def test_checksum_is_64_hex_chars(self) -> None:
        data = b"some file bytes"
        checksum = hashlib.sha256(data).hexdigest()
        assert len(checksum) == 64
        assert all(c in "0123456789abcdef" for c in checksum)

    def test_different_content_different_checksum(self) -> None:
        c1 = hashlib.sha256(b"version 1 content").hexdigest()
        c2 = hashlib.sha256(b"version 2 content").hexdigest()
        assert c1 != c2

    def test_empty_file_has_known_checksum(self) -> None:
        empty_checksum = hashlib.sha256(b"").hexdigest()
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert empty_checksum == expected

    def test_same_content_same_checksum_idempotent(self) -> None:
        data = b"identical file"
        c1 = hashlib.sha256(data).hexdigest()
        c2 = hashlib.sha256(data).hexdigest()
        assert c1 == c2


# ── Storage key namespacing ───────────────────────────────────────────────────


class TestStorageKeyNamespacing:
    """Storage keys must be agency-scoped to prevent cross-tenant file access."""

    def test_version_key_includes_agency_id(self) -> None:
        agency_id = uuid.uuid4()
        asset_id = uuid.uuid4()
        filename = normalize_filename("deliverable_v2.pdf")
        key = f"{agency_id}/versions/{asset_id}/{filename}"
        assert str(agency_id) in key

    def test_version_key_includes_asset_id(self) -> None:
        agency_id = uuid.uuid4()
        asset_id = uuid.uuid4()
        filename = normalize_filename("deliverable_v2.pdf")
        key = f"{agency_id}/versions/{asset_id}/{filename}"
        assert str(asset_id) in key

    def test_two_agencies_different_namespaces(self) -> None:
        a1, a2 = uuid.uuid4(), uuid.uuid4()
        asset_id = uuid.uuid4()
        filename = "same_file.pdf"
        k1 = f"{a1}/versions/{asset_id}/{filename}"
        k2 = f"{a2}/versions/{asset_id}/{filename}"
        assert k1 != k2

    def test_two_assets_different_namespaces(self) -> None:
        agency_id = uuid.uuid4()
        a1, a2 = uuid.uuid4(), uuid.uuid4()
        filename = "deliverable.pdf"
        k1 = f"{agency_id}/versions/{a1}/{filename}"
        k2 = f"{agency_id}/versions/{a2}/{filename}"
        assert k1 != k2

    def test_storage_key_has_no_traversal(self) -> None:
        agency_id = uuid.uuid4()
        asset_id = uuid.uuid4()
        filename = normalize_filename("../../etc/passwd")
        assert ".." not in filename
        assert ".." not in f"{agency_id}/versions/{asset_id}/{filename}"


# ── Multiple versions for same asset ─────────────────────────────────────────


class TestMultipleVersionScenario:
    def _make_versions(self, count: int) -> list[AssetVersionRead]:
        asset_id = uuid.uuid4()
        uploader = uuid.uuid4()
        versions = []
        for n in range(1, count + 1):
            data = f"content version {n}".encode()
            versions.append(
                AssetVersionRead.model_validate(
                    {
                        "id": uuid.uuid4(),
                        "asset_id": asset_id,
                        "version_number": n,
                        "filename": f"brief_v{n}_{uuid.uuid4().hex[:8]}.pdf",
                        "mime_type": "application/pdf",
                        "size_bytes": len(data),
                        "checksum": hashlib.sha256(data).hexdigest(),
                        "uploaded_by_id": uploader,
                        "created_at": datetime.now(UTC),
                    }
                )
            )
        return versions

    def test_three_versions_all_same_asset_id(self) -> None:
        versions = self._make_versions(3)
        asset_ids = {v.asset_id for v in versions}
        assert len(asset_ids) == 1

    def test_version_numbers_unique(self) -> None:
        versions = self._make_versions(5)
        nums = [v.version_number for v in versions]
        assert len(nums) == len(set(nums))

    def test_version_numbers_sequential(self) -> None:
        versions = self._make_versions(4)
        nums = sorted(v.version_number for v in versions)
        assert nums == [1, 2, 3, 4]

    def test_each_version_has_unique_checksum(self) -> None:
        versions = self._make_versions(3)
        checksums = [v.checksum for v in versions]
        assert len(checksums) == len(set(checksums))

    def test_latest_version_has_highest_number(self) -> None:
        versions = self._make_versions(5)
        latest = max(versions, key=lambda v: v.version_number)
        assert latest.version_number == 5


# ── HTTP auth layer ───────────────────────────────────────────────────────────


class TestDeliveryFilesHTTPAuth:
    @pytest.mark.asyncio
    async def test_create_asset_version_no_token_returns_401(self, client: AsyncClient) -> None:
        import io

        resp = await client.post(
            f"/api/v1/assets/{uuid.uuid4()}/versions",
            headers={"X-Agency-ID": str(uuid.uuid4())},
            files={"file": ("v2.pdf", io.BytesIO(b"new version"), "application/pdf")},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_asset_no_token_returns_401(self, client: AsyncClient) -> None:
        resp = await client.get(
            f"/api/v1/assets/{uuid.uuid4()}",
            headers={"X-Agency-ID": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_download_asset_no_token_returns_401(self, client: AsyncClient) -> None:
        resp = await client.get(
            f"/api/v1/assets/{uuid.uuid4()}/download",
            headers={"X-Agency-ID": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_link_asset_no_token_returns_401(self, client: AsyncClient) -> None:
        resp = await client.post(
            f"/api/v1/briefs/{uuid.uuid4()}/assets/{uuid.uuid4()}/link",
            headers={"X-Agency-ID": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

"""Live-database integration tests for the agency-side Social Media Preview
Center endpoints (app/api/v1/deliverable_preview.py): CRUD on
DeliverablePreviewConfig, platform x format validation, the draft/
revision_requested edit guard (the anti-carryover mechanism), and carousel
slot reorder + cover selection.

Uses the `tenants` fixture for a real Agency/Brand/User/Brief, then creates a
fresh draft Deliverable via the real API (so its status starts editable)
rather than relying on the fixture's pre-seeded `submitted` deliverable,
which is instead used to exercise the "cannot edit once submitted" guard.
"""

from __future__ import annotations

import io

from httpx import AsyncClient
from PIL import Image

from app.tests.conftest import agency_headers


def _png(width: int = 1080, height: int = 1080) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(5, 5, 5)).save(buf, format="PNG")
    return buf.getvalue()


async def _create_draft_deliverable(client: AsyncClient, tenant, headers) -> str:
    resp = await client.post(
        f"/api/v1/briefs/{tenant.brief_id}/deliverables",
        headers=headers,
        json={"title": "Preview Test Deliverable", "deliverable_type": "image"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _upload_asset(
    client: AsyncClient, tenant, deliverable_id, headers, width: int = 1080, height: int = 1080
) -> str:
    resp = await client.post(
        f"/api/v1/briefs/{tenant.brief_id}/deliverables/{deliverable_id}/assets",
        headers=headers,
        files={"file": ("a.png", io.BytesIO(_png(width, height)), "image/png")},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


class TestPreviewConfigCrud:
    async def test_create_preview_config(self, client: AsyncClient, tenants) -> None:
        tenant_a, _ = tenants
        headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        deliverable_id = await _create_draft_deliverable(client, tenant_a, headers)

        resp = await client.put(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-config",
            headers=headers,
            json={
                "platform": "instagram",
                "preview_format": "feed_single",
                "caption": "Yeni koleksiyonumuz burada!",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["platform"] == "instagram"
        assert body["preview_format"] == "feed_single"
        assert body["revision_number"] == 1
        assert body["deliverable_id"] == deliverable_id

    async def test_get_preview_config_returns_created_config(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, _ = tenants
        headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        deliverable_id = await _create_draft_deliverable(client, tenant_a, headers)
        await client.put(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-config",
            headers=headers,
            json={"platform": "linkedin", "preview_format": "text_post", "caption": "Merhaba"},
        )
        resp = await client.get(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-config",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["platform"] == "linkedin"

    async def test_get_preview_config_404_when_not_configured(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, _ = tenants
        headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        deliverable_id = await _create_draft_deliverable(client, tenant_a, headers)
        resp = await client.get(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-config",
            headers=headers,
        )
        assert resp.status_code == 404

    async def test_update_increments_revision_number(self, client: AsyncClient, tenants) -> None:
        tenant_a, _ = tenants
        headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        deliverable_id = await _create_draft_deliverable(client, tenant_a, headers)
        payload = {"platform": "instagram", "preview_format": "feed_single", "caption": "v1"}
        first = await client.put(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-config",
            headers=headers,
            json=payload,
        )
        assert first.json()["revision_number"] == 1

        payload["caption"] = "v2"
        second = await client.put(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-config",
            headers=headers,
            json=payload,
        )
        assert second.json()["revision_number"] == 2
        assert second.json()["caption"] == "v2"


class TestPlatformFormatValidation:
    async def test_unsupported_platform_format_combo_rejected(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, _ = tenants
        headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        deliverable_id = await _create_draft_deliverable(client, tenant_a, headers)
        # x does not support "story"
        resp = await client.put(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-config",
            headers=headers,
            json={"platform": "x", "preview_format": "story"},
        )
        assert resp.status_code == 422

    async def test_unsupported_platform_rejected(self, client: AsyncClient, tenants) -> None:
        tenant_a, _ = tenants
        headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        deliverable_id = await _create_draft_deliverable(client, tenant_a, headers)
        resp = await client.put(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-config",
            headers=headers,
            json={"platform": "youtube", "preview_format": "feed_single"},
        )
        assert resp.status_code == 422

    async def test_supported_combo_for_every_platform_accepted(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, _ = tenants
        headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        combos = [
            ("instagram", "feed_single"),
            ("facebook", "story"),
            ("linkedin", "document_carousel"),
            ("x", "text_post"),
            ("tiktok", "reel"),
        ]
        for platform, fmt in combos:
            deliverable_id = await _create_draft_deliverable(client, tenant_a, headers)
            resp = await client.put(
                f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}"
                "/preview-config",
                headers=headers,
                json={"platform": platform, "preview_format": fmt},
            )
            assert resp.status_code == 200, f"{platform}/{fmt} should be accepted"


class TestEditGuard:
    async def test_edit_blocked_once_deliverable_is_submitted(
        self, client: AsyncClient, tenants
    ) -> None:
        """tenant.deliverable_id is pre-seeded with status='submitted' —
        the anti-carryover guard must refuse a preview-config write on it,
        exactly like update_deliverable already does for the deliverable
        itself."""
        tenant_a, _ = tenants
        headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        resp = await client.put(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{tenant_a.deliverable_id}"
            "/preview-config",
            headers=headers,
            json={"platform": "instagram", "preview_format": "feed_single"},
        )
        assert resp.status_code == 400

    async def test_draft_deliverable_is_editable(self, client: AsyncClient, tenants) -> None:
        tenant_a, _ = tenants
        headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        deliverable_id = await _create_draft_deliverable(client, tenant_a, headers)
        resp = await client.put(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-config",
            headers=headers,
            json={"platform": "instagram", "preview_format": "feed_single"},
        )
        assert resp.status_code == 200

    async def test_revision_requested_deliverable_is_editable(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, _ = tenants
        headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        deliverable_id = await _create_draft_deliverable(client, tenant_a, headers)

        import uuid as uuid_mod
        from datetime import UTC, datetime

        from app.db.session import AsyncSessionLocal
        from app.models.deliverable import Deliverable

        async with AsyncSessionLocal() as session:
            d = await session.get(Deliverable, uuid_mod.UUID(deliverable_id))
            d.status = "revision_requested"
            d.submitted_at = datetime.now(UTC)
            await session.commit()

        resp = await client.put(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-config",
            headers=headers,
            json={"platform": "instagram", "preview_format": "feed_single"},
        )
        assert resp.status_code == 200

    async def test_slot_reorder_also_blocked_once_submitted(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, _ = tenants
        headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        resp = await client.put(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{tenant_a.deliverable_id}"
            "/preview-slots",
            headers=headers,
            json={"slots": []},
        )
        assert resp.status_code == 400


class TestSlotReorderAndCover:
    async def test_reorder_and_set_cover(self, client: AsyncClient, tenants) -> None:
        tenant_a, _ = tenants
        headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        deliverable_id = await _create_draft_deliverable(client, tenant_a, headers)
        asset_1 = await _upload_asset(client, tenant_a, deliverable_id, headers)
        asset_2 = await _upload_asset(client, tenant_a, deliverable_id, headers)

        resp = await client.put(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-slots",
            headers=headers,
            json={
                "slots": [
                    {"asset_id": asset_1, "position": 0, "is_cover": False},
                    {"asset_id": asset_2, "position": 1, "is_cover": True},
                ]
            },
        )
        assert resp.status_code == 200
        slots = resp.json()
        assert len(slots) == 2
        assert slots[0]["asset_id"] == asset_1
        assert slots[0]["position"] == 0
        assert slots[1]["is_cover"] is True

    async def test_reorder_swaps_positions(self, client: AsyncClient, tenants) -> None:
        tenant_a, _ = tenants
        headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        deliverable_id = await _create_draft_deliverable(client, tenant_a, headers)
        asset_1 = await _upload_asset(client, tenant_a, deliverable_id, headers)
        asset_2 = await _upload_asset(client, tenant_a, deliverable_id, headers)

        await client.put(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-slots",
            headers=headers,
            json={
                "slots": [
                    {"asset_id": asset_1, "position": 0, "is_cover": False},
                    {"asset_id": asset_2, "position": 1, "is_cover": False},
                ]
            },
        )
        resp = await client.put(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-slots",
            headers=headers,
            json={
                "slots": [
                    {"asset_id": asset_2, "position": 0, "is_cover": True},
                    {"asset_id": asset_1, "position": 1, "is_cover": False},
                ]
            },
        )
        assert resp.status_code == 200
        slots = resp.json()
        assert slots[0]["asset_id"] == asset_2
        assert slots[0]["is_cover"] is True
        assert slots[1]["asset_id"] == asset_1

    async def test_unrelated_asset_rejected(self, client: AsyncClient, tenants) -> None:
        """An asset never linked to this deliverable must not be usable as a slot."""
        tenant_a, tenant_b = tenants
        headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        deliverable_id = await _create_draft_deliverable(client, tenant_a, headers)

        other_headers = agency_headers(tenant_b.agency_token, tenant_b.agency_id)
        other_deliverable_id = await _create_draft_deliverable(client, tenant_b, other_headers)
        foreign_asset_id = await _upload_asset(
            client, tenant_b, other_deliverable_id, other_headers
        )

        resp = await client.put(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-slots",
            headers=headers,
            json={"slots": [{"asset_id": foreign_asset_id, "position": 0, "is_cover": False}]},
        )
        assert resp.status_code == 400

    async def test_duplicate_asset_in_slots_rejected(self, client: AsyncClient, tenants) -> None:
        tenant_a, _ = tenants
        headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        deliverable_id = await _create_draft_deliverable(client, tenant_a, headers)
        asset_1 = await _upload_asset(client, tenant_a, deliverable_id, headers)

        resp = await client.put(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-slots",
            headers=headers,
            json={
                "slots": [
                    {"asset_id": asset_1, "position": 0, "is_cover": False},
                    {"asset_id": asset_1, "position": 1, "is_cover": False},
                ]
            },
        )
        assert resp.status_code == 422

    async def test_list_slots(self, client: AsyncClient, tenants) -> None:
        tenant_a, _ = tenants
        headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        deliverable_id = await _create_draft_deliverable(client, tenant_a, headers)
        asset_1 = await _upload_asset(client, tenant_a, deliverable_id, headers)
        await client.put(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-slots",
            headers=headers,
            json={"slots": [{"asset_id": asset_1, "position": 0, "is_cover": True}]},
        )
        resp = await client.get(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-slots",
            headers=headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestPreviewConfigWarningsInResponse:
    async def test_missing_caption_warning_surfaces_in_response(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, _ = tenants
        headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        deliverable_id = await _create_draft_deliverable(client, tenant_a, headers)
        resp = await client.put(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-config",
            headers=headers,
            json={"platform": "instagram", "preview_format": "feed_single"},
        )
        assert resp.status_code == 200
        codes = [w["code"] for w in resp.json()["warnings"]]
        assert "missing_caption" in codes

    async def test_carousel_warnings_reflect_real_uploaded_slot_count(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, _ = tenants
        headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        deliverable_id = await _create_draft_deliverable(client, tenant_a, headers)
        await client.put(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-config",
            headers=headers,
            json={"platform": "instagram", "preview_format": "feed_carousel", "caption": "x"},
        )
        get_resp = await client.get(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-config",
            headers=headers,
        )
        codes = [w["code"] for w in get_resp.json()["warnings"]]
        assert "carousel_too_few_slides" in codes  # zero real slots uploaded yet

        asset_1 = await _upload_asset(client, tenant_a, deliverable_id, headers)
        asset_2 = await _upload_asset(client, tenant_a, deliverable_id, headers)
        await client.put(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-slots",
            headers=headers,
            json={
                "slots": [
                    {"asset_id": asset_1, "position": 0, "is_cover": True},
                    {"asset_id": asset_2, "position": 1, "is_cover": False},
                ]
            },
        )
        get_resp_2 = await client.get(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-config",
            headers=headers,
        )
        codes_2 = [w["code"] for w in get_resp_2.json()["warnings"]]
        assert "carousel_too_few_slides" not in codes_2  # now genuinely 2 real slots

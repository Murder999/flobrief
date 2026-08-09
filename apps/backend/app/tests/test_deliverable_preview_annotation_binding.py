"""Confirms an annotation pin stays bound to the correct asset across
carousel slot reorder and platform-view switches.

DeliverableAnnotation.asset_id already binds a pin to one specific asset
regardless of platform view or carousel order — the plan's design explicitly
requires no model changes here. This test proves the *data contract* holds
at the API layer (that reordering slots or switching preview platform/format
never mutates an existing annotation's asset_id); the frontend's
PreviewAssetStage.tsx is what actually resolves the currently-displayed
slide's asset_id and filters annotations by it.
"""

from __future__ import annotations

import io

from httpx import AsyncClient
from PIL import Image

from app.tests.conftest import agency_headers


def _png(seed: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (600, 600), color=(seed, seed, seed)).save(buf, format="PNG")
    return buf.getvalue()


async def _create_draft_deliverable(client: AsyncClient, tenant, headers) -> str:
    resp = await client.post(
        f"/api/v1/briefs/{tenant.brief_id}/deliverables",
        headers=headers,
        json={"title": "Annotation Binding Deliverable", "deliverable_type": "image"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _upload_asset(client: AsyncClient, tenant, deliverable_id, headers, seed: int) -> str:
    resp = await client.post(
        f"/api/v1/briefs/{tenant.brief_id}/deliverables/{deliverable_id}/assets",
        headers=headers,
        files={"file": (f"a{seed}.png", io.BytesIO(_png(seed)), "image/png")},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


class TestAnnotationStaysBoundAcrossReorderAndPlatformSwitch:
    async def test_pin_asset_id_unaffected_by_slot_reorder_and_platform_switch(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, _ = tenants
        headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        deliverable_id = await _create_draft_deliverable(client, tenant_a, headers)

        asset_1 = await _upload_asset(client, tenant_a, deliverable_id, headers, 10)
        asset_2 = await _upload_asset(client, tenant_a, deliverable_id, headers, 20)

        # Pin an annotation to asset_1 specifically.
        ann_resp = await client.post(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/annotations",
            headers=headers,
            json={
                "asset_id": asset_1,
                "version_number": 1,
                "x_percent": 25.0,
                "y_percent": 40.0,
                "annotation_type": "general",
                "visibility": "client_visible",
                "body": "Bu alanı büyütelim",
            },
        )
        assert ann_resp.status_code == 201
        annotation_id = ann_resp.json()["id"]
        assert ann_resp.json()["asset_id"] == asset_1

        # Configure carousel preview with both assets, asset_1 first.
        await client.put(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-config",
            headers=headers,
            json={"platform": "instagram", "preview_format": "feed_carousel", "caption": "c"},
        )
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

        # Reorder: asset_2 becomes the cover / first slide.
        reorder_resp = await client.put(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-slots",
            headers=headers,
            json={
                "slots": [
                    {"asset_id": asset_2, "position": 0, "is_cover": True},
                    {"asset_id": asset_1, "position": 1, "is_cover": False},
                ]
            },
        )
        assert reorder_resp.status_code == 200

        # Switch platform/format entirely.
        switch_resp = await client.put(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-config",
            headers=headers,
            json={"platform": "facebook", "preview_format": "feed_carousel", "caption": "c2"},
        )
        assert switch_resp.status_code == 200

        # The annotation must still point at asset_1, untouched by any of this.
        list_resp = await client.get(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/annotations",
            headers=headers,
        )
        assert list_resp.status_code == 200
        anns = list_resp.json()
        assert len(anns) == 1
        assert anns[0]["id"] == annotation_id
        assert anns[0]["asset_id"] == asset_1

        # And the slot for asset_1 now correctly reports position=1 (post-reorder).
        slots_resp = await client.get(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-slots",
            headers=headers,
        )
        slot_for_asset_1 = next(s for s in slots_resp.json() if s["asset_id"] == asset_1)
        assert slot_for_asset_1["position"] == 1

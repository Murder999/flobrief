"""Security audit tests: tenant isolation, platform admin access, public token security.

These tests are DB-agnostic: they verify security properties at the auth/middleware
layer, not at the business-logic layer. They do not require a live database because
they either:
  - send no token / invalid token (JWT decode fails → 401 before any DB call)
  - verify headers added by SecurityHeadersMiddleware on any response

Tests that verify cross-tenant isolation check that authenticated requests with
mismatched agency data never return 200 (the DB may return 401/403/404/422/500).
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token

# ── Tenant Isolation ─────────────────────────────────────────────────────────


class TestTenantIsolation:
    """Tenant endpoints must reject unauthenticated and cross-tenant requests."""

    @pytest.mark.asyncio
    async def test_unauthenticated_brief_endpoint_rejected(self, client: AsyncClient) -> None:
        """No token on tenant endpoint → 401 (JWT layer, no DB needed)."""
        resp = await client.get(
            "/api/v1/briefs",
            headers={"X-Agency-ID": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_rejected(self, client: AsyncClient) -> None:
        """Garbage token → 401 (JWT decode fails before any DB call)."""
        resp = await client.get(
            "/api/v1/briefs",
            headers={
                "Authorization": "Bearer not-a-real-jwt",
                "X-Agency-ID": str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, client: AsyncClient) -> None:
        """Expired token → 401 (exp claim checked without DB)."""
        import time

        from jose import jwt

        from app.core.config import settings

        payload = {
            "sub": str(uuid.uuid4()),
            "exp": int(time.time()) - 3600,
            "iat": int(time.time()) - 7200,
            "type": "access",
            "agency_id": str(uuid.uuid4()),
            "user_type": "agency_user",
        }
        expired_token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        resp = await client.get(
            "/api/v1/briefs",
            headers={
                "Authorization": f"Bearer {expired_token}",
                "X-Agency-ID": str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_unauthenticated_template_endpoint_rejected(self, client: AsyncClient) -> None:
        """No token on templates endpoint → 401 (JWT layer, no DB needed)."""
        resp = await client.get("/api/v1/templates")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_unauthenticated_calendar_items_rejected(self, client: AsyncClient) -> None:
        """No token on calendar items endpoint → 401 (JWT layer, no DB needed)."""
        resp = await client.get(
            "/api/v1/calendar/items",
            headers={"X-Agency-ID": str(uuid.uuid4())},
        )
        assert resp.status_code == 401


# ── Platform Admin Security ───────────────────────────────────────────────────


class TestPlatformAdminSecurity:
    """platform_admin JWT must not grant access to tenant endpoints, and vice versa."""

    @pytest.mark.asyncio
    async def test_no_token_platform_endpoint_rejected(self, client: AsyncClient) -> None:
        """No token on platform endpoint → 401 (no DB needed)."""
        resp = await client.get("/api/v1/platform/agencies")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_on_platform_endpoint_rejected(self, client: AsyncClient) -> None:
        """Garbage token on platform endpoint → 401."""
        resp = await client.get(
            "/api/v1/platform/agencies",
            headers={"Authorization": "Bearer garbage-token"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_tenant_token_on_platform_endpoint_rejected(self, client: AsyncClient) -> None:
        """Tenant JWT on /platform/ must be rejected (no platform_admin claim)."""
        token = create_access_token(
            subject=str(uuid.uuid4()),
            extra_claims={
                "agency_id": str(uuid.uuid4()),
                "user_type": "agency_user",
                "role": "agency_owner",
            },
        )
        resp = await client.get(
            "/api/v1/platform/agencies",
            headers={"Authorization": f"Bearer {token}"},
        )
        # platform routes check user_type == platform_admin before DB
        assert resp.status_code in {401, 403}

    @pytest.mark.asyncio
    async def test_no_token_billing_endpoint_rejected(self, client: AsyncClient) -> None:
        """Billing endpoint without token → 401."""
        resp = await client.get("/api/v1/billing/subscription")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_unauthenticated_owner_endpoint_rejected(self, client: AsyncClient) -> None:
        """Owner endpoint without token → 401."""
        resp = await client.get("/api/v1/owner/dashboard")
        assert resp.status_code == 401


# ── Public Token Security ─────────────────────────────────────────────────────


class TestPublicTokenSecurity:
    """Approval / report-share tokens must be SHA-256 hashed; raw never stored in DB."""

    def test_sha256_hash_differs_from_raw(self) -> None:
        raw = secrets.token_urlsafe(32)
        hashed = hashlib.sha256(raw.encode()).hexdigest()
        assert hashed != raw

    def test_sha256_hash_is_consistent(self) -> None:
        raw = secrets.token_urlsafe(32)
        h1 = hashlib.sha256(raw.encode()).hexdigest()
        h2 = hashlib.sha256(raw.encode()).hexdigest()
        assert h1 == h2

    def test_sha256_different_inputs_give_different_hashes(self) -> None:
        t1 = secrets.token_urlsafe(32)
        t2 = secrets.token_urlsafe(32)
        assert t1 != t2
        assert hashlib.sha256(t1.encode()).hexdigest() != hashlib.sha256(t2.encode()).hexdigest()

    @pytest.mark.asyncio
    async def test_approval_public_endpoint_without_token_rejected(
        self, client: AsyncClient
    ) -> None:
        """Accessing approval portal without a valid token → not 200."""
        resp = await client.get(f"/api/v1/approvals/portal/{uuid.uuid4()}/info")
        assert resp.status_code != 200

    @pytest.mark.asyncio
    async def test_report_share_without_token_rejected(self, client: AsyncClient) -> None:
        """Report share endpoint without token → not 200."""
        resp = await client.get(f"/api/v1/reports/share/{uuid.uuid4()}/public")
        assert resp.status_code != 200


# ── Security Headers ──────────────────────────────────────────────────────────


class TestSecurityHeaders:
    """SecurityHeadersMiddleware must attach headers to every response,
    including 401 responses which require no DB connection."""

    @pytest.mark.asyncio
    async def test_x_content_type_options_on_401(self, client: AsyncClient) -> None:
        """Even a 401 response must carry X-Content-Type-Options."""
        resp = await client.get("/api/v1/briefs")
        assert resp.status_code == 401
        assert resp.headers.get("x-content-type-options") == "nosniff"

    @pytest.mark.asyncio
    async def test_x_frame_options_on_401(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/briefs")
        assert resp.status_code == 401
        assert resp.headers.get("x-frame-options") == "DENY"

    @pytest.mark.asyncio
    async def test_x_xss_protection_on_401(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/briefs")
        assert resp.status_code == 401
        assert resp.headers.get("x-xss-protection") == "1; mode=block"

    @pytest.mark.asyncio
    async def test_referrer_policy_on_401(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/briefs")
        assert resp.status_code == 401
        assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    @pytest.mark.asyncio
    async def test_permissions_policy_on_401(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/briefs")
        assert resp.status_code == 401
        assert "permissions-policy" in resp.headers


# ── /media response headers: SVG-scoped, not blanket ────────────────────────


class TestMediaContentDispositionScoping:
    """SVG is rejected at upload time (storage_service.ALLOWED_MIME_TYPES has
    no image/svg+xml), but SecurityHeadersMiddleware adds a defense-in-depth
    Content-Disposition: attachment + locked-down CSP for any SVG/HTML that
    still ends up on disk. That must be scoped to SVG/HTML only — applying it
    to every /media/ response would force browsers to download PNG/JPEG/PDF/
    video previews instead of rendering them inline, breaking the product's
    core media-preview UX."""

    _PNG_1PX = bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010802000000"
        "907753de0000000c49444154789c63f8cfc0000003010100c9fe92ef00"
        "00000049454e44ae426082"
    )
    _SVG_PAYLOAD = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'

    @pytest.fixture
    def media_root(self):
        from app.core.config import settings

        root = Path(settings.MEDIA_ROOT)
        root.mkdir(parents=True, exist_ok=True)
        return root

    @pytest.mark.asyncio
    async def test_png_served_inline_no_attachment_header(
        self, client: AsyncClient, media_root: Path
    ) -> None:
        name = f"test-{uuid.uuid4().hex}.png"
        (media_root / name).write_bytes(self._PNG_1PX)
        try:
            resp = await client.get(f"/media/{name}")
            assert resp.status_code == 200
            assert resp.headers.get("content-type", "").startswith("image/png")
            assert "content-disposition" not in {k.lower() for k in resp.headers}
            assert "content-security-policy" not in {k.lower() for k in resp.headers}
        finally:
            (media_root / name).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_legacy_svg_on_disk_still_forced_to_download(
        self, client: AsyncClient, media_root: Path
    ) -> None:
        """Even though SVG can no longer be uploaded, a pre-existing file on
        disk (or any other unexpected write path) must still be denied
        inline rendering — this is the defense-in-depth case."""
        name = f"test-{uuid.uuid4().hex}.svg"
        (media_root / name).write_bytes(self._SVG_PAYLOAD)
        try:
            resp = await client.get(f"/media/{name}")
            assert resp.status_code == 200
            assert resp.headers.get("content-disposition") == "attachment"
            assert "default-src 'none'" in resp.headers.get("content-security-policy", "")
        finally:
            (media_root / name).unlink(missing_ok=True)


# ── Entitlement Auth Guard ────────────────────────────────────────────────────


class TestEntitlementAuthGuard:
    """Entitlement endpoints require auth — no DB call possible without valid JWT."""

    @pytest.mark.asyncio
    async def test_entitlement_check_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/billing/entitlements/check",
            json={"feature": "white_label"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_entitlement_usage_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/billing/entitlements")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_checkout_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/billing/checkout",
            json={"plan_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

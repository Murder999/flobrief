"""Tests for platform admin security foundation."""

import sys
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.repositories.platform_audit_log import PlatformAuditLogRepository

# Make scripts importable in tests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


class TestPlatformAuditLogRepository:
    def test_has_no_update_method(self) -> None:
        assert not hasattr(PlatformAuditLogRepository, "update")

    def test_has_no_delete_method(self) -> None:
        assert not hasattr(PlatformAuditLogRepository, "delete")

    def test_has_no_soft_delete_method(self) -> None:
        assert not hasattr(PlatformAuditLogRepository, "soft_delete")

    def test_has_create_method(self) -> None:
        assert hasattr(PlatformAuditLogRepository, "create")

    def test_has_list_method(self) -> None:
        assert hasattr(PlatformAuditLogRepository, "list")


@pytest.mark.asyncio
async def test_platform_health_requires_auth(client: AsyncClient) -> None:
    """Platform health endpoint must return 401 when no token is provided."""
    response = await client.get("/api/v1/platform/health")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_platform_health_rejects_invalid_token(client: AsyncClient) -> None:
    """Platform health endpoint must return 401 for a garbage token."""
    response = await client.get(
        "/api/v1/platform/health",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_platform_health_rejects_non_admin_jwt(client: AsyncClient) -> None:
    """A valid JWT with user_type=agency_user must be rejected with 403."""
    from app.core.security import create_access_token

    token = create_access_token(
        subject="test-user-id",
        extra_claims={"user_type": "agency_user"},
    )
    response = await client.get(
        "/api/v1/platform/health",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


class TestSeedPlansData:
    def test_five_plans_defined(self) -> None:
        from scripts.seed_plans import PLAN_DEFINITIONS as plans

        assert len(plans) == 5

    def test_all_plan_codes_present(self) -> None:
        from scripts.seed_plans import PLAN_DEFINITIONS as plans

        codes = {p["code"] for p in plans}
        assert codes == {"starter_agency", "pro_agency", "agency_plus", "brand_solo", "enterprise"}

    def test_plans_are_idempotent_by_code(self) -> None:
        from scripts.seed_plans import PLAN_DEFINITIONS as plans

        codes = [p["code"] for p in plans]
        assert len(codes) == len(set(codes)), "Duplicate plan codes in seed data"

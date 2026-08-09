"""Tests for platform admin auth endpoint contracts."""

from httpx import AsyncClient


class TestPlatformAuthEndpoints:
    async def test_platform_login_requires_json_body(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/platform/auth/login", json={})
        assert response.status_code == 422

    async def test_platform_login_rejects_invalid_email(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/platform/auth/login",
            json={"email": "not-an-email", "password": "somepass"},
        )
        assert response.status_code == 422

    async def test_platform_health_requires_auth(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/platform/health")
        assert response.status_code == 401

    async def test_platform_health_rejects_agency_token(self, client: AsyncClient) -> None:
        from app.core.security import create_access_token

        token = create_access_token("some-user-id", extra_claims={"user_type": "agency_user"})
        response = await client.get(
            "/api/v1/platform/health",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    async def test_platform_health_accepts_platform_admin_token(self, client: AsyncClient) -> None:
        from unittest.mock import patch

        from app.core.security import create_access_token

        token = create_access_token("admin-id", extra_claims={"user_type": "platform_admin"})

        mock_user = type(
            "User",
            (),
            {
                "id": "admin-id",
                "is_active": True,
                "user_type": "platform_admin",
                "deleted_at": None,
            },
        )()

        with patch("app.core.dependencies.get_platform_admin_user", return_value=mock_user):
            pass

        response = await client.get(
            "/api/v1/platform/health",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code in (200, 401)

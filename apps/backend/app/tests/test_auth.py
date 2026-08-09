"""Tests for auth schemas, password policy, JWT logic, and endpoint contracts."""

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from app.core.security import create_access_token, decode_access_token
from app.models.enums import UserType
from app.schemas.auth import (
    ChangePasswordRequest,
    PasswordResetConfirm,
    RegisterRequest,
)
from app.services.password_service import (
    is_password_valid,
    validate_password_policy,
)
from app.services.token_service import (
    generate_token,
    get_access_token_expire_minutes,
    get_refresh_token_expires,
    hash_token,
)


class TestPasswordPolicy:
    def test_too_short_rejected(self) -> None:
        errors = validate_password_policy("Short1!")
        assert any("10 karakter" in e for e in errors)

    def test_no_uppercase_rejected(self) -> None:
        errors = validate_password_policy("lowercase1!")
        assert any("büyük harf" in e for e in errors)

    def test_no_lowercase_rejected(self) -> None:
        errors = validate_password_policy("UPPERCASE1!")
        assert any("küçük harf" in e for e in errors)

    def test_no_digit_rejected(self) -> None:
        errors = validate_password_policy("NoDigits!!!")
        assert any("rakam" in e for e in errors)

    def test_no_special_char_rejected(self) -> None:
        errors = validate_password_policy("NoSpecial123")
        assert any("özel karakter" in e for e in errors)

    def test_common_password_rejected(self) -> None:
        errors = validate_password_policy("Password1!")
        assert any("yaygın" in e for e in errors)

    def test_valid_password_passes(self) -> None:
        assert is_password_valid("Flobrief@2024#Secure") is True

    def test_valid_password_no_errors(self) -> None:
        assert validate_password_policy("Flobrief@2024#Secure") == []


class TestRegisterRequestSchema:
    def test_email_normalized_to_lowercase(self) -> None:
        req = RegisterRequest(
            email="UPPER@EXAMPLE.COM",
            full_name="Test User",
            password="Flobrief@2024#",
        )
        assert req.email == "upper@example.com"

    def test_email_stripped(self) -> None:
        req = RegisterRequest(
            email="  user@example.com  ",
            full_name="Test",
            password="Flobrief@2024#",
        )
        assert req.email == "user@example.com"

    def test_full_name_stripped(self) -> None:
        req = RegisterRequest(
            email="a@b.com",
            full_name="  Test User  ",
            password="Flobrief@2024#",
        )
        assert req.full_name == "Test User"

    def test_weak_password_raises(self) -> None:
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", full_name="Test", password="weak")

    def test_no_user_type_field(self) -> None:
        fields = RegisterRequest.model_fields
        assert "user_type" not in fields

    def test_short_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", full_name="X", password="Flobrief@2024#")


class TestPasswordResetSchema:
    def test_weak_new_password_raises(self) -> None:
        with pytest.raises(ValidationError):
            PasswordResetConfirm(token="abc", new_password="short")

    def test_valid_new_password_passes(self) -> None:
        req = PasswordResetConfirm(token="abc", new_password="Flobrief@2024#")
        assert req.new_password == "Flobrief@2024#"


class TestChangePasswordSchema:
    def test_user_can_choose_valid_new_password(self) -> None:
        req = ChangePasswordRequest(
            current_password="Current@2024#",
            new_password="MyChosen@2026#",
        )
        assert req.new_password == "MyChosen@2026#"

    def test_weak_new_password_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ChangePasswordRequest(current_password="Current@2024#", new_password="weak")

    def test_current_password_is_required(self) -> None:
        with pytest.raises(ValidationError):
            ChangePasswordRequest(current_password="", new_password="MyChosen@2026#")


class TestJWTClaims:
    def test_access_token_has_user_type(self) -> None:
        token = create_access_token("user-id", extra_claims={"user_type": "agency_user"})
        payload = decode_access_token(token)
        assert payload["user_type"] == "agency_user"

    def test_platform_admin_token_has_correct_user_type(self) -> None:
        token = create_access_token("admin-id", extra_claims={"user_type": "platform_admin"})
        payload = decode_access_token(token)
        assert payload["user_type"] == "platform_admin"

    def test_platform_admin_token_has_no_agency_id(self) -> None:
        token = create_access_token("admin-id", extra_claims={"user_type": "platform_admin"})
        payload = decode_access_token(token)
        assert "agency_id" not in payload
        assert "role" not in payload

    def test_platform_admin_shorter_access_expiry(self) -> None:
        admin_minutes = get_access_token_expire_minutes(UserType.PLATFORM_ADMIN.value)
        user_minutes = get_access_token_expire_minutes(UserType.AGENCY_USER.value)
        assert admin_minutes < user_minutes
        assert admin_minutes == 5
        assert user_minutes == 15

    def test_platform_admin_shorter_refresh_expiry(self) -> None:
        admin_exp = get_refresh_token_expires(UserType.PLATFORM_ADMIN.value)
        user_exp = get_refresh_token_expires(UserType.AGENCY_USER.value)
        assert admin_exp < user_exp

    def test_expire_minutes_param_respected(self) -> None:
        token_5 = create_access_token("sub", expire_minutes=5)
        token_60 = create_access_token("sub", expire_minutes=60)
        p5 = decode_access_token(token_5)
        p60 = decode_access_token(token_60)
        assert p5["exp"] < p60["exp"]


class TestTokenService:
    def test_hash_token_deterministic(self) -> None:
        t = "my-secret-token"
        assert hash_token(t) == hash_token(t)

    def test_hash_token_length(self) -> None:
        assert len(hash_token("abc")) == 64

    def test_different_tokens_different_hashes(self) -> None:
        assert hash_token("token-a") != hash_token("token-b")

    def test_generate_token_length(self) -> None:
        t = generate_token(48)
        assert len(t) > 20

    def test_generate_tokens_unique(self) -> None:
        assert generate_token() != generate_token()


class TestAuthEndpointContracts:
    async def test_me_returns_401_without_token(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    async def test_change_password_requires_auth(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "Current@2024#",
                "new_password": "MyChosen@2026#",
            },
        )
        assert response.status_code == 401

    async def test_platform_change_password_requires_auth(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/platform/auth/change-password",
            json={
                "current_password": "Current@2024#",
                "new_password": "MyChosen@2026#",
            },
        )
        assert response.status_code == 401

    async def test_refresh_returns_401_without_cookie(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/auth/refresh")
        assert response.status_code == 401

    async def test_logout_succeeds_without_cookie(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/auth/logout")
        assert response.status_code == 200

    async def test_register_validates_weak_password(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "full_name": "Test User", "password": "weak"},
        )
        assert response.status_code == 422

    async def test_register_validates_email_format(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "full_name": "Test User",
                "password": "Flobrief@2024#",
            },
        )
        assert response.status_code == 422

    async def test_login_validates_required_fields(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/auth/login", json={})
        assert response.status_code == 422

    async def test_verify_email_requires_token_field(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/auth/verify-email", json={})
        assert response.status_code == 422

    async def test_forgot_password_validates_email(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "not-an-email"},
        )
        assert response.status_code == 422

    async def test_reset_password_validates_new_password(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": "some-token", "new_password": "weak"},
        )
        assert response.status_code == 422

    async def test_me_verified_returns_403_without_token(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/auth/me/verified")
        assert response.status_code == 401


class TestPlatformAdminBlock:
    def test_register_schema_has_no_user_type(self) -> None:
        fields = {name: field for name, field in RegisterRequest.model_fields.items()}
        assert "user_type" not in fields

    def test_platform_admin_token_shorter_than_user_token(self) -> None:
        admin_mins = get_access_token_expire_minutes("platform_admin")
        user_mins = get_access_token_expire_minutes("agency_user")
        assert admin_mins == 5
        assert user_mins == 15
        assert admin_mins < user_mins

    def test_platform_admin_user_type_value(self) -> None:
        assert UserType.PLATFORM_ADMIN.value == "platform_admin"

    def test_agency_user_type_value(self) -> None:
        assert UserType.AGENCY_USER.value == "agency_user"

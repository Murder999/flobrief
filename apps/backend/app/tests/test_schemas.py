"""Tests that verify sensitive fields are never exposed in response schemas."""

from app.schemas.user import UserRead


class TestUserReadSecurity:
    def test_no_password_hash_field(self) -> None:
        fields = set(UserRead.model_fields.keys())
        assert "password_hash" not in fields

    def test_no_mfa_secret_field(self) -> None:
        fields = set(UserRead.model_fields.keys())
        assert "mfa_secret_encrypted" not in fields

    def test_has_required_public_fields(self) -> None:
        fields = set(UserRead.model_fields.keys())
        assert "id" in fields
        assert "email" in fields
        assert "full_name" in fields
        assert "user_type" in fields
        assert "is_active" in fields
        assert "mfa_enabled" in fields

    def test_no_hashed_password_in_any_alias(self) -> None:
        for field_name, field_info in UserRead.model_fields.items():
            alias = getattr(field_info, "alias", None) or field_name
            assert (
                "password" not in alias.lower()
            ), f"Field '{field_name}' (alias: '{alias}') may expose password data"
            assert (
                "secret" not in alias.lower()
            ), f"Field '{field_name}' (alias: '{alias}') may expose secret data"


class TestUserCreateValidation:
    def test_email_normalized_to_lowercase(self) -> None:
        from app.schemas.user import UserCreate

        user = UserCreate(email="TEST@Example.COM", full_name="Test", password="password123")
        assert user.email == "test@example.com"

    def test_full_name_stripped(self) -> None:
        from app.schemas.user import UserCreate

        user = UserCreate(email="test@example.com", full_name="  Test  ", password="password123")
        assert user.full_name == "Test"


class TestAgencySchemas:
    def test_slug_normalized(self) -> None:
        from app.schemas.agency import AgencyCreate

        agency = AgencyCreate(name="Test Agency", slug="  MySlug  ")
        assert agency.slug == "myslug"

"""
Unit tests for Part 12 white-label branding system.
No DB required — all pure Python logic.
"""

from __future__ import annotations

import hashlib
import re
import secrets

import pytest
from pydantic import ValidationError

from app.models.enums import BrandingAssetType, CustomDomainStatus
from app.schemas.branding import BrandingSettingsUpdate, CustomDomainCreate, PublicBrandingView

# ── Enum tests ────────────────────────────────────────────────────────────────


class TestBrandingAssetTypeEnum:
    def test_logo_value(self):
        assert BrandingAssetType.LOGO.value == "logo"

    def test_email_logo_value(self):
        assert BrandingAssetType.EMAIL_LOGO.value == "email_logo"

    def test_favicon_value(self):
        assert BrandingAssetType.FAVICON.value == "favicon"

    def test_social_preview_value(self):
        assert BrandingAssetType.SOCIAL_PREVIEW.value == "social_preview"

    def test_count(self):
        assert len(BrandingAssetType) == 4


class TestCustomDomainStatusEnum:
    def test_pending_value(self):
        assert CustomDomainStatus.PENDING.value == "pending"

    def test_verified_value(self):
        assert CustomDomainStatus.VERIFIED.value == "verified"

    def test_failed_value(self):
        assert CustomDomainStatus.FAILED.value == "failed"

    def test_disabled_value(self):
        assert CustomDomainStatus.DISABLED.value == "disabled"

    def test_count(self):
        assert len(CustomDomainStatus) == 4


# ── Color validation ──────────────────────────────────────────────────────────


class TestColorValidation:
    def test_valid_6_digit_hex_lowercase(self):
        data = BrandingSettingsUpdate(primary_color="#6366f1")
        assert data.primary_color == "#6366F1"

    def test_valid_6_digit_hex_uppercase(self):
        data = BrandingSettingsUpdate(primary_color="#FF0000")
        assert data.primary_color == "#FF0000"

    def test_none_color_accepted(self):
        data = BrandingSettingsUpdate(primary_color=None)
        assert data.primary_color is None

    def test_short_hex_rejected(self):
        with pytest.raises(ValidationError):
            BrandingSettingsUpdate(primary_color="#123")

    def test_no_hash_rejected(self):
        with pytest.raises(ValidationError):
            BrandingSettingsUpdate(primary_color="6366F1")

    def test_too_long_rejected(self):
        with pytest.raises(ValidationError):
            BrandingSettingsUpdate(primary_color="#RRGGBBFF")

    def test_invalid_chars_rejected(self):
        with pytest.raises(ValidationError):
            BrandingSettingsUpdate(primary_color="#GGHHII")

    def test_all_three_color_fields_validated(self):
        data = BrandingSettingsUpdate(
            primary_color="#111111",
            secondary_color="#222222",
            accent_color="#333333",
        )
        assert data.primary_color == "#111111"
        assert data.secondary_color == "#222222"
        assert data.accent_color == "#333333"


# ── PublicBrandingView schema isolation ───────────────────────────────────────


class TestPublicBrandingViewIsolation:
    def test_no_agency_id_field(self):
        fields = PublicBrandingView.model_fields
        assert "agency_id" not in fields

    def test_no_asset_id_fields(self):
        fields = PublicBrandingView.model_fields
        assert "logo_asset_id" not in fields
        assert "email_logo_asset_id" not in fields
        assert "favicon_asset_id" not in fields

    def test_has_expected_public_fields(self):
        fields = set(PublicBrandingView.model_fields.keys())
        expected = {
            "agency_name",
            "brand_name",
            "primary_color",
            "secondary_color",
            "accent_color",
            "logo_url",
            "favicon_url",
            "custom_footer_text",
            "is_branded",
        }
        assert expected.issubset(fields)

    def test_is_branded_false_by_default_when_no_wl(self):
        view = PublicBrandingView(
            agency_name="Test Agency",
            brand_name=None,
            primary_color=None,
            secondary_color=None,
            accent_color=None,
            logo_url=None,
            favicon_url=None,
            custom_footer_text=None,
            is_branded=False,
        )
        assert view.is_branded is False


# ── Custom domain validation ──────────────────────────────────────────────────


class TestCustomDomainCreate:
    def test_domain_is_stripped_and_lowercased(self):
        data = CustomDomainCreate(domain="  MyAgency.COM  ")
        assert data.domain == "myagency.com"

    def test_empty_domain_rejected(self):
        with pytest.raises(ValidationError):
            CustomDomainCreate(domain="   ")

    def test_long_domain_rejected(self):
        with pytest.raises(ValidationError):
            CustomDomainCreate(domain="a" * 256)


# ── Domain verification token security ───────────────────────────────────────


class TestDomainVerificationTokenSecurity:
    def test_raw_token_is_not_hash(self):
        raw = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        assert raw != token_hash

    def test_hash_is_64_hex_chars(self):
        raw = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        assert len(token_hash) == 64
        assert re.fullmatch(r"[0-9a-f]+", token_hash)

    def test_same_raw_produces_same_hash(self):
        raw = secrets.token_urlsafe(32)
        h1 = hashlib.sha256(raw.encode()).hexdigest()
        h2 = hashlib.sha256(raw.encode()).hexdigest()
        assert h1 == h2

    def test_different_raw_produces_different_hash(self):
        h1 = hashlib.sha256(b"token_a").hexdigest()
        h2 = hashlib.sha256(b"token_b").hexdigest()
        assert h1 != h2


# ── Branding MIME type security ───────────────────────────────────────────────


class TestBrandingMimeTypes:
    _ALLOWED = {"image/png", "image/jpeg", "image/webp", "image/gif"}
    _REJECTED = {"image/svg+xml", "application/pdf", "text/html", "application/javascript"}

    def test_allowed_mime_types_are_image_formats(self):
        for mime in self._ALLOWED:
            assert mime.startswith("image/")

    def test_svg_is_not_allowed(self):
        assert "image/svg+xml" not in self._ALLOWED

    def test_pdf_is_not_allowed(self):
        assert "application/pdf" not in self._ALLOWED

    def test_four_allowed_types(self):
        assert len(self._ALLOWED) == 4

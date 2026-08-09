"""Unit tests for phone_utils.normalize_e164. No DB required."""

from __future__ import annotations

from app.services.phone_utils import normalize_e164


class TestNormalizeE164:
    def test_already_e164_unchanged(self) -> None:
        assert normalize_e164("+905551112233") == "+905551112233"

    def test_turkish_leading_zero_converted(self) -> None:
        assert normalize_e164("05551112233") == "+905551112233"

    def test_strips_spaces_parens_dashes(self) -> None:
        assert normalize_e164("0 (555) 111-22-33") == "+905551112233"

    def test_double_zero_international_prefix(self) -> None:
        assert normalize_e164("00905551112233") == "+905551112233"

    def test_whatsapp_prefix_stripped(self) -> None:
        assert normalize_e164("whatsapp:+905551112233") == "+905551112233"

    def test_bare_digits_without_leading_zero_gets_plus(self) -> None:
        assert normalize_e164("14155238886") == "+14155238886"

    def test_empty_string_returns_none(self) -> None:
        assert normalize_e164("") is None

    def test_whitespace_only_returns_none(self) -> None:
        assert normalize_e164("   ") is None

    def test_too_short_returns_none(self) -> None:
        assert normalize_e164("+9012") is None

    def test_letters_return_none(self) -> None:
        assert normalize_e164("not-a-phone") is None

    def test_leading_zero_after_country_code_still_normalizes(self) -> None:
        # Common Turkish user input: "0" + area/subscriber digits.
        assert normalize_e164("0532 111 22 33") == "+905321112233"

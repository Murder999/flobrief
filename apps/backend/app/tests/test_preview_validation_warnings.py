"""Tests for app.services.preview_validation_service.compute_preview_warnings.

compute_preview_warnings is a pure function — these are direct unit tests of
its logic with representative arguments (the same shape build_preview_config_read
passes in from real DeliverablePreviewConfig/DeliverablePreviewSlot/Asset rows
in the live-DB tests in test_deliverable_preview.py). No warning is ever
stored; it is always recomputed from whatever real data is passed in, so a
warning that stops applying (e.g. a caption that used to be missing gets
filled in) simply stops appearing on the next computation.
"""

from __future__ import annotations

import uuid

from app.services.preview_validation_service import SlotAssetInfo, compute_preview_warnings


def _slot(
    width: int | None = 1080, height: int | None = 1080, position: int = 0, is_cover: bool = False
) -> SlotAssetInfo:
    return SlotAssetInfo(
        asset_id=uuid.uuid4(),
        position=position,
        is_cover=is_cover,
        width_px=width,
        height_px=height,
    )


class TestMissingCaption:
    def test_no_caption_produces_info_warning(self) -> None:
        warnings = compute_preview_warnings(
            platform="instagram",
            preview_format="feed_single",
            caption=None,
            hashtags=None,
            slots=[_slot()],
        )
        assert any(w.code == "missing_caption" for w in warnings)

    def test_blank_caption_produces_warning(self) -> None:
        warnings = compute_preview_warnings(
            platform="instagram",
            preview_format="feed_single",
            caption="   ",
            hashtags=None,
            slots=[_slot()],
        )
        assert any(w.code == "missing_caption" for w in warnings)

    def test_present_caption_has_no_missing_caption_warning(self) -> None:
        warnings = compute_preview_warnings(
            platform="instagram",
            preview_format="feed_single",
            caption="Yeni ürünümüz burada!",
            hashtags=None,
            slots=[_slot()],
        )
        assert not any(w.code == "missing_caption" for w in warnings)


class TestCaptionLength:
    def test_x_caption_over_280_chars_warns(self) -> None:
        warnings = compute_preview_warnings(
            platform="x",
            preview_format="text_post",
            caption="a" * 300,
            hashtags=None,
            slots=[],
        )
        assert any(w.code == "caption_too_long" for w in warnings)

    def test_x_caption_under_280_chars_no_warning(self) -> None:
        warnings = compute_preview_warnings(
            platform="x",
            preview_format="text_post",
            caption="a" * 100,
            hashtags=None,
            slots=[],
        )
        assert not any(w.code == "caption_too_long" for w in warnings)

    def test_instagram_allows_longer_caption(self) -> None:
        """Same length that trips X's limit should not trip Instagram's."""
        warnings = compute_preview_warnings(
            platform="instagram",
            preview_format="feed_single",
            caption="a" * 300,
            hashtags=None,
            slots=[_slot()],
        )
        assert not any(w.code == "caption_too_long" for w in warnings)


class TestHashtagLimits:
    def test_too_many_hashtags_for_linkedin_warns(self) -> None:
        warnings = compute_preview_warnings(
            platform="linkedin",
            preview_format="feed_single",
            caption="body",
            hashtags=[f"#tag{i}" for i in range(10)],
            slots=[_slot()],
        )
        assert any(w.code == "too_many_hashtags" for w in warnings)

    def test_hashtags_within_limit_no_warning(self) -> None:
        warnings = compute_preview_warnings(
            platform="linkedin",
            preview_format="feed_single",
            caption="body",
            hashtags=["#a", "#b"],
            slots=[_slot()],
        )
        assert not any(w.code == "too_many_hashtags" for w in warnings)

    def test_no_hashtags_no_warning(self) -> None:
        warnings = compute_preview_warnings(
            platform="instagram",
            preview_format="feed_single",
            caption="body",
            hashtags=None,
            slots=[_slot()],
        )
        assert not any(w.code == "too_many_hashtags" for w in warnings)


class TestCarouselSlideCount:
    def test_carousel_with_one_slide_warns_too_few(self) -> None:
        warnings = compute_preview_warnings(
            platform="instagram",
            preview_format="feed_carousel",
            caption="c",
            hashtags=None,
            slots=[_slot()],
        )
        assert any(w.code == "carousel_too_few_slides" for w in warnings)

    def test_carousel_with_two_slides_no_too_few_warning(self) -> None:
        warnings = compute_preview_warnings(
            platform="instagram",
            preview_format="feed_carousel",
            caption="c",
            hashtags=None,
            slots=[_slot(position=0), _slot(position=1)],
        )
        assert not any(w.code == "carousel_too_few_slides" for w in warnings)

    def test_carousel_over_platform_max_warns(self) -> None:
        slots = [_slot(position=i) for i in range(11)]  # instagram max is 10
        warnings = compute_preview_warnings(
            platform="instagram",
            preview_format="feed_carousel",
            caption="c",
            hashtags=None,
            slots=slots,
        )
        assert any(w.code == "carousel_too_many_slides" for w in warnings)

    def test_x_carousel_max_is_four(self) -> None:
        slots = [_slot(position=i) for i in range(5)]
        warnings = compute_preview_warnings(
            platform="x",
            preview_format="feed_carousel",
            caption="c",
            hashtags=None,
            slots=slots,
        )
        assert any(w.code == "carousel_too_many_slides" for w in warnings)

    def test_non_carousel_format_never_checks_slide_count(self) -> None:
        warnings = compute_preview_warnings(
            platform="instagram",
            preview_format="feed_single",
            caption="c",
            hashtags=None,
            slots=[],
        )
        assert not any(
            w.code in ("carousel_too_few_slides", "carousel_too_many_slides") for w in warnings
        )


class TestMissingCover:
    def test_carousel_without_cover_warns(self) -> None:
        slots = [_slot(position=0, is_cover=False), _slot(position=1, is_cover=False)]
        warnings = compute_preview_warnings(
            platform="instagram",
            preview_format="feed_carousel",
            caption="c",
            hashtags=None,
            slots=slots,
        )
        assert any(w.code == "missing_cover" for w in warnings)

    def test_carousel_with_cover_selected_no_warning(self) -> None:
        slots = [_slot(position=0, is_cover=True), _slot(position=1, is_cover=False)]
        warnings = compute_preview_warnings(
            platform="instagram",
            preview_format="feed_carousel",
            caption="c",
            hashtags=None,
            slots=slots,
        )
        assert not any(w.code == "missing_cover" for w in warnings)

    def test_empty_slots_does_not_warn_missing_cover(self) -> None:
        """No slots at all yet (nothing uploaded) is a different condition
        than 'slides exist but none chosen as cover' — must not double-warn."""
        warnings = compute_preview_warnings(
            platform="instagram",
            preview_format="feed_carousel",
            caption="c",
            hashtags=None,
            slots=[],
        )
        assert not any(w.code == "missing_cover" for w in warnings)


class TestAspectRatioMismatch:
    def test_story_format_expects_9_16_and_warns_on_square_image(self) -> None:
        square = _slot(width=1080, height=1080)
        warnings = compute_preview_warnings(
            platform="instagram",
            preview_format="story",
            caption="c",
            hashtags=None,
            slots=[square],
        )
        assert any(w.code == "aspect_ratio_mismatch" for w in warnings)

    def test_story_format_accepts_real_9_16_image(self) -> None:
        portrait = _slot(width=1080, height=1920)
        warnings = compute_preview_warnings(
            platform="instagram",
            preview_format="story",
            caption="c",
            hashtags=None,
            slots=[portrait],
        )
        assert not any(w.code == "aspect_ratio_mismatch" for w in warnings)

    def test_missing_dimensions_never_fabricates_a_ratio_warning(self) -> None:
        """An asset whose width/height extraction failed (None/None) must be
        silently skipped, never treated as a violation."""
        unknown = _slot(width=None, height=None)
        warnings = compute_preview_warnings(
            platform="instagram",
            preview_format="story",
            caption="c",
            hashtags=None,
            slots=[unknown],
        )
        assert not any(w.code == "aspect_ratio_mismatch" for w in warnings)

    def test_combination_with_no_configured_range_never_warns(self) -> None:
        """ "grid" has no configured aspect-ratio range for facebook (only
        instagram's grid format is configured) — must not fabricate an
        expectation for a combination nobody defined one for, even with a
        wildly non-square image that would fail almost any real ratio check."""
        extreme = _slot(width=50, height=5000)
        warnings = compute_preview_warnings(
            platform="facebook",
            preview_format="grid",
            caption="c",
            hashtags=None,
            slots=[extreme],
        )
        assert not any(w.code == "aspect_ratio_mismatch" for w in warnings)


class TestWarningsRecomputedNotStored:
    def test_warnings_disappear_once_underlying_data_changes(self) -> None:
        """Same function, same platform/format — only the input caption changes.
        Proves warnings are derived fresh each call rather than cached/stale."""
        no_caption = compute_preview_warnings(
            platform="instagram",
            preview_format="feed_single",
            caption=None,
            hashtags=None,
            slots=[_slot()],
        )
        with_caption = compute_preview_warnings(
            platform="instagram",
            preview_format="feed_single",
            caption="Artık başlığımız var",
            hashtags=None,
            slots=[_slot()],
        )
        assert any(w.code == "missing_caption" for w in no_caption)
        assert not any(w.code == "missing_caption" for w in with_caption)

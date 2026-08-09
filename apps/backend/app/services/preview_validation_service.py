"""Pure functions computing Social Media Preview Center validation warnings.

Every warning is derived strictly from real ``DeliverablePreviewConfig``/
``DeliverablePreviewSlot``/``Asset`` data passed in by the caller — nothing
here fabricates a value. Warnings are always recomputed on read, never
stored, so they can never go stale. They are internal heuristics for the
agency/brand to sanity-check a preview before submission, not enforced
platform limits (the real platforms may change their limits at any time;
see ``PreviewValidationPanel.tsx`` on the frontend for the same disclaimer).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.models.deliverable_preview import DeliverablePreviewConfig, DeliverablePreviewSlot
from app.schemas.deliverable_preview import PreviewConfigRead, PreviewWarning

# Soft caption-length guidance per platform (characters). Not the platform's
# actual hard limit in every case (e.g. Instagram truncates in-feed well
# before its 2200 char hard cap) — labelled as such in the warning message.
_CAPTION_SOFT_LIMITS: dict[str, int] = {
    "instagram": 2200,
    "facebook": 63206,
    "linkedin": 3000,
    "x": 280,
    "tiktok": 2200,
}

_HASHTAG_SOFT_LIMITS: dict[str, int] = {
    "instagram": 30,
    "facebook": 30,
    "linkedin": 5,
    "x": 10,
    "tiktok": 30,
}

_CAROUSEL_FORMATS: set[str] = {"feed_carousel", "grid", "document_carousel"}
_CAROUSEL_MIN_SLIDES = 2

_CAROUSEL_MAX_SLIDES: dict[str, dict[str, int]] = {
    "instagram": {"feed_carousel": 10, "grid": 10},
    "linkedin": {"document_carousel": 20, "feed_carousel": 10},
    "x": {"feed_carousel": 4},
    "facebook": {"feed_carousel": 10},
}

# (min_ratio, max_ratio) of width/height per (platform, preview_format).
# Only ever compared against an asset that actually has extracted width_px/
# height_px — never fabricated for assets missing dimensions. Combinations
# with no entry here simply skip the aspect-ratio check, on purpose.
_ASPECT_RATIO_RANGES: dict[tuple[str, str], tuple[float, float]] = {
    ("instagram", "feed_single"): (0.79, 1.92),
    ("instagram", "feed_carousel"): (0.79, 1.92),
    ("instagram", "story"): (0.54, 0.57),
    ("instagram", "reel"): (0.54, 0.57),
    ("instagram", "reel_cover"): (0.54, 0.57),
    ("instagram", "grid"): (0.95, 1.05),
    ("facebook", "feed_single"): (0.79, 1.92),
    ("facebook", "feed_carousel"): (0.79, 1.92),
    ("facebook", "story"): (0.54, 0.57),
    ("tiktok", "reel"): (0.54, 0.57),
    ("tiktok", "reel_cover"): (0.54, 0.57),
    ("linkedin", "feed_single"): (0.56, 1.92),
    ("linkedin", "feed_carousel"): (0.95, 1.05),
    ("linkedin", "document_carousel"): (0.7, 1.43),
    ("x", "feed_single"): (0.5, 2.0),
    ("x", "feed_carousel"): (0.5, 2.0),
}


@dataclass(frozen=True)
class SlotAssetInfo:
    """Real, already-persisted slide data — never synthesized by this module."""

    asset_id: uuid.UUID
    position: int
    is_cover: bool
    width_px: int | None
    height_px: int | None


def compute_preview_warnings(
    *,
    platform: str,
    preview_format: str,
    caption: str | None,
    hashtags: list[str] | None,
    slots: list[SlotAssetInfo],
) -> list[PreviewWarning]:
    warnings: list[PreviewWarning] = []

    if not caption or not caption.strip():
        warnings.append(
            PreviewWarning(
                code="missing_caption",
                message="Bu format için başlık/açıklama girilmemiş.",
                severity="info",
            )
        )
    else:
        soft_limit = _CAPTION_SOFT_LIMITS.get(platform)
        if soft_limit is not None and len(caption) > soft_limit:
            warnings.append(
                PreviewWarning(
                    code="caption_too_long",
                    message=(
                        f"Başlık {len(caption)} karakter — {platform} için önerilen "
                        f"üst sınır {soft_limit} karakter (dahili tahmini bir öneridir)."
                    ),
                    severity="warning",
                )
            )

    if hashtags:
        soft_hashtag_limit = _HASHTAG_SOFT_LIMITS.get(platform)
        if soft_hashtag_limit is not None and len(hashtags) > soft_hashtag_limit:
            warnings.append(
                PreviewWarning(
                    code="too_many_hashtags",
                    message=(
                        f"{len(hashtags)} hashtag girildi — {platform} için önerilen "
                        f"üst sınır {soft_hashtag_limit} (dahili tahmini bir öneridir)."
                    ),
                    severity="warning",
                )
            )

    if preview_format in _CAROUSEL_FORMATS:
        slide_count = len(slots)
        if slide_count < _CAROUSEL_MIN_SLIDES:
            warnings.append(
                PreviewWarning(
                    code="carousel_too_few_slides",
                    message=(
                        f"Bu format için en az {_CAROUSEL_MIN_SLIDES} görsel/slayt önerilir "
                        f"(şu an {slide_count})."
                    ),
                    severity="warning",
                )
            )
        max_slides = _CAROUSEL_MAX_SLIDES.get(platform, {}).get(preview_format)
        if max_slides is not None and slide_count > max_slides:
            warnings.append(
                PreviewWarning(
                    code="carousel_too_many_slides",
                    message=(
                        f"{slide_count} slayt girildi — {platform} için önerilen üst sınır "
                        f"{max_slides} (dahili tahmini bir öneridir)."
                    ),
                    severity="warning",
                )
            )
        if slots and not any(s.is_cover for s in slots):
            warnings.append(
                PreviewWarning(
                    code="missing_cover",
                    message="Karüsel için kapak görseli seçilmemiş.",
                    severity="info",
                )
            )

    ratio_range = _ASPECT_RATIO_RANGES.get((platform, preview_format))
    if ratio_range is not None:
        min_ratio, max_ratio = ratio_range
        for slot in slots:
            if slot.width_px is None or slot.height_px is None or slot.height_px == 0:
                continue
            ratio = slot.width_px / slot.height_px
            if not (min_ratio <= ratio <= max_ratio):
                warnings.append(
                    PreviewWarning(
                        code="aspect_ratio_mismatch",
                        message=(
                            f"#{slot.position + 1} numaralı görselin en-boy oranı "
                            f"({slot.width_px}x{slot.height_px}) bu format için önerilen "
                            "aralığın dışında (dahili tahmini bir öneridir)."
                        ),
                        severity="warning",
                    )
                )

    return warnings


async def build_preview_config_read(
    config: DeliverablePreviewConfig,
    db: AsyncSession,
) -> PreviewConfigRead:
    """Assemble the API read model, including freshly recomputed warnings.

    Loads the deliverable's current slots and their assets' real width_px/
    height_px straight from the DB — warnings are never stored on the config
    row, so they can never go stale relative to the underlying asset data.
    """
    slot_rows = (
        (
            await db.execute(
                select(DeliverablePreviewSlot)
                .where(
                    DeliverablePreviewSlot.deliverable_id == config.deliverable_id,
                    DeliverablePreviewSlot.deleted_at.is_(None),
                )
                .order_by(DeliverablePreviewSlot.position.asc())
            )
        )
        .scalars()
        .all()
    )

    asset_ids = [s.asset_id for s in slot_rows]
    dims: dict[uuid.UUID, tuple[int | None, int | None]] = {}
    if asset_ids:
        asset_rows = (
            await db.execute(
                select(Asset.id, Asset.width_px, Asset.height_px).where(Asset.id.in_(asset_ids))
            )
        ).all()
        dims = {row.id: (row.width_px, row.height_px) for row in asset_rows}

    slot_infos = [
        SlotAssetInfo(
            asset_id=s.asset_id,
            position=s.position,
            is_cover=s.is_cover,
            width_px=dims.get(s.asset_id, (None, None))[0],
            height_px=dims.get(s.asset_id, (None, None))[1],
        )
        for s in slot_rows
    ]

    warnings = compute_preview_warnings(
        platform=config.platform,
        preview_format=config.preview_format,
        caption=config.caption,
        hashtags=config.hashtags,
        slots=slot_infos,
    )

    return PreviewConfigRead(
        id=config.id,
        agency_id=config.agency_id,
        brand_id=config.brand_id,
        brief_id=config.brief_id,
        deliverable_id=config.deliverable_id,
        platform=config.platform,
        preview_format=config.preview_format,
        caption=config.caption,
        title=config.title,
        cta_label=config.cta_label,
        hashtags=config.hashtags,
        display_name_override=config.display_name_override,
        profile_photo_asset_id=config.profile_photo_asset_id,
        cover_asset_id=config.cover_asset_id,
        revision_number=config.revision_number,
        created_by_id=config.created_by_id,
        updated_by_id=config.updated_by_id,
        created_at=config.created_at,
        updated_at=config.updated_at,
        warnings=warnings,
    )

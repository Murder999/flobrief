"""Pure helper for extracting image pixel dimensions at upload time.

Used by every asset-creation call site (AssetService.upload/create_version,
deliverables.upload_deliverable_asset) so ``Asset.width_px``/``height_px`` and
``AssetVersion.width_px``/``height_px`` get populated for images. Video
duration extraction is intentionally out of scope for this pass (no ffmpeg
dependency) — video assets simply keep ``width_px``/``height_px`` as ``None``.
"""

from __future__ import annotations

import io
import logging

from PIL import Image

logger = logging.getLogger(__name__)


def extract_image_dimensions(data: bytes, mime: str) -> tuple[int, int] | None:
    """Return ``(width, height)`` for an image payload, or ``None``.

    Defensive by design: corrupt files, unsupported formats, non-image mime
    types, or any Pillow decoding error must never break the upload path that
    calls this — they simply mean no dimensions are recorded.
    """
    if not mime.startswith("image/"):
        return None
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
        # Image.verify() leaves the file object unusable for further access,
        # so re-open to actually read width/height.
        with Image.open(io.BytesIO(data)) as img:
            width, height = img.size
        if width <= 0 or height <= 0:
            return None
        return (width, height)
    except Exception:
        logger.debug("extract_image_dimensions: could not decode image", exc_info=True)
        return None

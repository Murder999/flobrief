"""Storage abstraction: local disk now, cloud-ready interface for S3/R2 later."""

from __future__ import annotations

import os
import re
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from fastapi import HTTPException

from app.core.config import settings

# ── Allowed MIME types ────────────────────────────────────────────────────────

ALLOWED_MIME_TYPES: frozenset[str] = frozenset(
    {
        # Images
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/bmp",
        "image/tiff",
        # Documents
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        # Text / data
        "text/plain",
        "text/csv",
        # Archives
        "application/zip",
        "application/x-zip-compressed",
        # Video
        "video/mp4",
        "video/quicktime",
        "video/webm",
        # Audio
        "audio/mpeg",
        "audio/wav",
        "audio/ogg",
        # Design tools
        "image/vnd.adobe.photoshop",
        "application/postscript",
    }
)

_UNSAFE = re.compile(r"[^\w\-_.]")


def normalize_filename(original: str) -> str:
    """Strip directory traversal, sanitize chars, keep extension, add UUID suffix."""
    # Treat both POSIX and Windows separators as path boundaries regardless of
    # the server OS. ``os.path.basename`` alone does not strip backslashes on
    # Linux, which could preserve Windows-style traversal segments.
    base = os.path.basename(original.replace("\\", "/"))
    name, dot, ext = base.rpartition(".")
    if not name:
        name = base
        dot = ""
        ext = ""
    safe_name = _UNSAFE.sub("_", name)[:80]
    safe_ext = _UNSAFE.sub("", ext)[:10].lower()
    uid = uuid.uuid4().hex[:8]
    if safe_ext:
        return f"{safe_name}_{uid}{dot}{safe_ext}"
    return f"{safe_name}_{uid}"


def validate_mime_type(mime_type: str) -> None:
    """Raise 422 if MIME type is not on the allowlist."""
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"File type '{mime_type}' is not permitted.",
        )


def validate_file_size(size_bytes: int) -> None:
    """Raise 422 if file exceeds MAX_UPLOAD_SIZE_MB."""
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if size_bytes > max_bytes:
        raise HTTPException(
            status_code=422,
            detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB} MB.",
        )


# ── Storage backend interface ─────────────────────────────────────────────────


class StorageBackend(ABC):
    @abstractmethod
    async def save(self, data: bytes, storage_key: str) -> None: ...

    @abstractmethod
    async def delete(self, storage_key: str) -> None: ...

    @abstractmethod
    def get_path(self, storage_key: str) -> str: ...


class LocalStorageBackend(StorageBackend):
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    async def save(self, data: bytes, storage_key: str) -> None:
        dest = self.root / storage_key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    async def delete(self, storage_key: str) -> None:
        target = self.root / storage_key
        if target.exists():
            target.unlink()

    def get_path(self, storage_key: str) -> str:
        return str(self.root / storage_key)


def get_storage_backend() -> StorageBackend:
    backend = settings.STORAGE_BACKEND.lower()
    if backend == "local":
        return LocalStorageBackend(settings.MEDIA_ROOT)
    raise NotImplementedError(f"Storage backend '{backend}' is not yet implemented.")

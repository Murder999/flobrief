"""Unit tests for comment/thread schemas, asset storage utilities, and enum values.

No DB required — all pure Python logic.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.enums import (
    CommentVisibility,
    StorageProvider,
    ThreadStatus,
    ThreadType,
)
from app.schemas.comment import AddCommentRequest, ThreadCreate, UpdateCommentRequest
from app.services.storage_service import (
    ALLOWED_MIME_TYPES,
    normalize_filename,
    validate_file_size,
    validate_mime_type,
)

# ── Enum value tests ──────────────────────────────────────────────────────────


def test_thread_type_values() -> None:
    assert ThreadType.BRIEF == "brief"
    assert ThreadType.FIELD == "field"
    assert ThreadType.ASSET == "asset"
    assert ThreadType.APPROVAL == "approval"


def test_thread_status_values() -> None:
    assert ThreadStatus.OPEN == "open"
    assert ThreadStatus.RESOLVED == "resolved"


def test_comment_visibility_values() -> None:
    assert CommentVisibility.INTERNAL == "internal"
    assert CommentVisibility.CLIENT_VISIBLE == "client_visible"


def test_storage_provider_values() -> None:
    assert StorageProvider.LOCAL == "local"
    assert StorageProvider.S3 == "s3"
    assert StorageProvider.R2 == "r2"


# ── Schema validation tests ───────────────────────────────────────────────────


def test_add_comment_empty_body_raises() -> None:
    with pytest.raises(ValidationError):
        AddCommentRequest(body="   ", visibility="internal")


def test_add_comment_body_too_long_raises() -> None:
    with pytest.raises(ValidationError):
        AddCommentRequest(body="x" * 50_001, visibility="internal")


def test_add_comment_strips_body_whitespace() -> None:
    req = AddCommentRequest(body="  revize lütfen  ", visibility="internal")
    assert req.body == "revize lütfen"


def test_add_comment_invalid_visibility_raises() -> None:
    with pytest.raises(ValidationError):
        AddCommentRequest(body="valid body", visibility="public")


def test_add_comment_internal_visibility_valid() -> None:
    req = AddCommentRequest(body="agency-only note", visibility="internal")
    assert req.visibility == "internal"


def test_add_comment_client_visible_visibility_valid() -> None:
    req = AddCommentRequest(body="message for brand", visibility="client_visible")
    assert req.visibility == "client_visible"


def test_update_comment_empty_body_raises() -> None:
    with pytest.raises(ValidationError):
        UpdateCommentRequest(body="")


def test_thread_create_invalid_type_raises() -> None:
    with pytest.raises(ValidationError):
        ThreadCreate(
            thread_type="invalid_type",
            initial_comment="Hello",
            visibility="internal",
        )


def test_thread_create_empty_initial_comment_raises() -> None:
    with pytest.raises(ValidationError):
        ThreadCreate(thread_type="brief", initial_comment="  ", visibility="internal")


# ── Storage security tests ─────────────────────────────────────────────────────


def test_normalize_filename_no_path_traversal() -> None:
    result = normalize_filename("../../etc/passwd.txt")
    assert ".." not in result
    assert result.endswith(".txt")


def test_normalize_filename_absolute_path_stripped() -> None:
    result = normalize_filename("/var/www/secret.pdf")
    assert "/" not in result
    assert result.endswith(".pdf")


def test_normalize_filename_spaces_replaced() -> None:
    result = normalize_filename("my photo file.png")
    assert " " not in result


def test_normalize_filename_preserves_extension() -> None:
    result = normalize_filename("brief_document.pdf")
    assert result.endswith(".pdf")


def test_normalize_filename_unique_each_call() -> None:
    a = normalize_filename("file.jpg")
    b = normalize_filename("file.jpg")
    assert a != b  # UUID suffix ensures uniqueness


def test_validate_mime_type_image_passes() -> None:
    validate_mime_type("image/jpeg")  # must not raise


def test_validate_mime_type_pdf_passes() -> None:
    validate_mime_type("application/pdf")  # must not raise


def test_validate_mime_type_disallowed_raises() -> None:
    with pytest.raises(HTTPException) as exc_info:
        validate_mime_type("application/x-executable")
    assert exc_info.value.status_code == 422


def test_validate_mime_type_script_disallowed() -> None:
    with pytest.raises(HTTPException):
        validate_mime_type("text/javascript")


def test_validate_file_size_over_limit_raises() -> None:
    # Default MAX_UPLOAD_SIZE_MB = 10, so 11 MB must fail
    with pytest.raises(HTTPException) as exc_info:
        validate_file_size(11 * 1024 * 1024)
    assert exc_info.value.status_code == 422


def test_validate_file_size_within_limit_passes() -> None:
    validate_file_size(5 * 1024 * 1024)  # 5 MB — must not raise


def test_allowed_mime_types_non_empty() -> None:
    assert len(ALLOWED_MIME_TYPES) > 0
    assert "image/jpeg" in ALLOWED_MIME_TYPES
    assert "application/pdf" in ALLOWED_MIME_TYPES

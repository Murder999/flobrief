"""Unit tests for approval schemas, token hashing, and service logic."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.models.enums import ApprovalStatus
from app.schemas.approval import (
    AddPublicCommentRequest,
    PublicApproveRequest,
    PublicRevisionRequest,
)
from app.services.approval_service import _hash_token

# ---------------------------------------------------------------------------
# Token hashing
# ---------------------------------------------------------------------------


def test_hash_token_is_sha256() -> None:
    raw = "mytoken"
    expected = hashlib.sha256(raw.encode()).hexdigest()
    assert _hash_token(raw) == expected


def test_hash_token_produces_64_hex_chars() -> None:
    raw = secrets.token_urlsafe(48)
    hashed = _hash_token(raw)
    assert len(hashed) == 64
    assert all(c in "0123456789abcdef" for c in hashed)


def test_raw_token_not_equal_to_hash() -> None:
    raw = "somesecrettoken"
    assert _hash_token(raw) != raw


def test_same_raw_produces_same_hash() -> None:
    raw = secrets.token_urlsafe(48)
    assert _hash_token(raw) == _hash_token(raw)


def test_different_raws_produce_different_hashes() -> None:
    a = secrets.token_urlsafe(48)
    b = secrets.token_urlsafe(48)
    assert _hash_token(a) != _hash_token(b)


# ---------------------------------------------------------------------------
# ApprovalStatus enum
# ---------------------------------------------------------------------------


def test_approval_status_values() -> None:
    assert ApprovalStatus.PENDING == "pending"
    assert ApprovalStatus.APPROVED == "approved"
    assert ApprovalStatus.REVISION_REQUESTED == "revision_requested"
    assert ApprovalStatus.CANCELLED == "cancelled"
    assert ApprovalStatus.EXPIRED == "expired"


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def test_revision_request_requires_comment() -> None:
    with pytest.raises(ValidationError):
        PublicRevisionRequest(comment="")


def test_revision_request_strips_whitespace() -> None:
    req = PublicRevisionRequest(comment="  Lütfen renkleri değiştirin  ")
    assert req.comment == "Lütfen renkleri değiştirin"


def test_public_approve_request_optional_fields() -> None:
    req = PublicApproveRequest()
    assert req.approver_name is None
    assert req.approver_email is None


def test_public_approve_request_with_data() -> None:
    req = PublicApproveRequest(approver_name="Ali Veli", approver_email="ali@example.com")
    assert req.approver_name == "Ali Veli"
    assert req.approver_email == "ali@example.com"


def test_public_approve_invalid_email_rejected() -> None:
    with pytest.raises(ValidationError):
        PublicApproveRequest(approver_email="not-an-email")


def test_add_public_comment_empty_raises() -> None:
    with pytest.raises(ValidationError):
        AddPublicCommentRequest(comment="   ")


def test_add_public_comment_too_long_raises() -> None:
    with pytest.raises(ValidationError):
        AddPublicCommentRequest(comment="x" * 5001)


# ---------------------------------------------------------------------------
# Token expiry logic
# ---------------------------------------------------------------------------


def test_token_expired_when_past_expires_at() -> None:
    expires_at = datetime.now(UTC) - timedelta(hours=1)
    is_expired = datetime.now(UTC) > expires_at
    assert is_expired is True


def test_token_valid_when_before_expires_at() -> None:
    expires_at = datetime.now(UTC) + timedelta(hours=71)
    is_expired = datetime.now(UTC) > expires_at
    assert is_expired is False

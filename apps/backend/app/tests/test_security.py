import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_secure_token,
    hash_password,
    verify_password,
)


def test_password_hash_and_verify() -> None:
    password = "SuperSecret123!"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("WrongPassword", hashed)


def test_access_token_roundtrip() -> None:
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    token = create_access_token(subject=user_id)
    payload = decode_access_token(token)
    assert payload["sub"] == user_id
    assert payload["type"] == "access"


def test_access_token_with_extra_claims() -> None:
    token = create_access_token(
        subject="user-123",
        extra_claims={"agency_id": "agency-456", "role": "agency_owner"},
    )
    payload = decode_access_token(token)
    assert payload["agency_id"] == "agency-456"
    assert payload["role"] == "agency_owner"


def test_invalid_token_raises() -> None:
    with pytest.raises(ValueError, match="Invalid or expired token"):
        decode_access_token("not.a.valid.token")


def test_secure_token_length() -> None:
    token = generate_secure_token(64)
    assert len(token) > 64

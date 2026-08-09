"""Tests for app/core/rate_limiter.py against the real local Redis instance
(REDIS_URL — the same one the app uses; no mock).
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.core.rate_limiter import (
    _enforce,
    _normalize_account_key,
    _reset,
    get_redis_client,
)


def _unique_key(label: str) -> str:
    return f"test:ratelimit:{label}:{uuid.uuid4().hex}"


class TestEnforce:
    async def test_allows_up_to_max_attempts(self) -> None:
        key = _unique_key("allow")
        try:
            for _ in range(3):
                await _enforce(key=key, max_attempts=3, window_seconds=60)
        finally:
            client = get_redis_client()
            await client.delete(key)

    async def test_blocks_after_max_attempts_with_429_and_retry_after(self) -> None:
        key = _unique_key("block")
        try:
            for _ in range(3):
                await _enforce(key=key, max_attempts=3, window_seconds=60)
            with pytest.raises(HTTPException) as exc_info:
                await _enforce(key=key, max_attempts=3, window_seconds=60)
            assert exc_info.value.status_code == 429
            assert "Retry-After" in exc_info.value.headers
            retry_after = int(exc_info.value.headers["Retry-After"])
            assert 0 < retry_after <= 60
        finally:
            client = get_redis_client()
            await client.delete(key)

    async def test_reset_clears_counter(self) -> None:
        key = _unique_key("reset")
        try:
            for _ in range(3):
                await _enforce(key=key, max_attempts=3, window_seconds=60)
            await _reset(key)
            # Should not raise — counter was cleared, back to attempt 1.
            await _enforce(key=key, max_attempts=3, window_seconds=60)
        finally:
            client = get_redis_client()
            await client.delete(key)

    async def test_fail_open_when_redis_unreachable(self, monkeypatch) -> None:
        def _broken_redis():
            raise ConnectionError("redis unreachable")

        monkeypatch.setattr("app.core.rate_limiter._get_redis", _broken_redis)
        # Must not raise — fail_closed defaults to False.
        await _enforce(key=_unique_key("failopen"), max_attempts=1, window_seconds=60)

    async def test_fail_closed_when_redis_unreachable(self, monkeypatch) -> None:
        def _broken_redis():
            raise ConnectionError("redis unreachable")

        monkeypatch.setattr("app.core.rate_limiter._get_redis", _broken_redis)
        with pytest.raises(HTTPException) as exc_info:
            await _enforce(
                key=_unique_key("failclosed"),
                max_attempts=1,
                window_seconds=60,
                fail_closed=True,
            )
        assert exc_info.value.status_code == 503


class TestAccountKeyNormalization:
    def test_case_insensitive(self) -> None:
        assert _normalize_account_key("User@Example.com") == _normalize_account_key(
            "user@example.com"
        )

    def test_whitespace_insensitive(self) -> None:
        assert _normalize_account_key("  user@example.com  ") == _normalize_account_key(
            "user@example.com"
        )

    def test_different_accounts_different_keys(self) -> None:
        assert _normalize_account_key("a@example.com") != _normalize_account_key("b@example.com")

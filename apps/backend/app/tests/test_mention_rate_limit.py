"""Tests for the mention-candidates rate limiter
(`app.core.rate_limiter.rate_limit_mention_candidates`) against the real
local Redis instance (no mock) — mirrors the pattern in test_rate_limiter.py.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.core.rate_limiter import get_redis_client, rate_limit_mention_candidates

pytestmark = pytest.mark.asyncio


def _unique_account_id() -> str:
    return f"test-mentions-{uuid.uuid4().hex}"


async def test_allows_up_to_60_requests_then_blocks_with_429_and_retry_after() -> None:
    account_id = _unique_account_id()
    key = f"ratelimit:mentions:acct:{account_id}"
    try:
        for _ in range(60):
            await rate_limit_mention_candidates(account_id)
        with pytest.raises(HTTPException) as exc_info:
            await rate_limit_mention_candidates(account_id)
        assert exc_info.value.status_code == 429
        assert "Retry-After" in exc_info.value.headers
        retry_after = int(exc_info.value.headers["Retry-After"])
        assert 0 < retry_after <= 60
    finally:
        await get_redis_client().delete(key)


async def test_different_accounts_have_independent_buckets() -> None:
    """One user hammering the endpoint must not exhaust another user's — or
    another tenant's — quota (no shared/cross-account bucket)."""
    account_a = _unique_account_id()
    account_b = _unique_account_id()
    key_a = f"ratelimit:mentions:acct:{account_a}"
    key_b = f"ratelimit:mentions:acct:{account_b}"
    try:
        for _ in range(60):
            await rate_limit_mention_candidates(account_a)
        with pytest.raises(HTTPException):
            await rate_limit_mention_candidates(account_a)

        # account_b is untouched — still well under its own limit.
        await rate_limit_mention_candidates(account_b)
    finally:
        await get_redis_client().delete(key_a)
        await get_redis_client().delete(key_b)

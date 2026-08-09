"""Server-side revocation tracking for platform-admin impersonation tokens.

Impersonation tokens are short-lived signed JWTs, but a bare JWT can't be
revoked before its natural expiry. This module tracks the single active
impersonation `jti` per admin in Redis so that:

- Ending impersonation immediately invalidates the token (not just client
  amnesia — `get_current_user` checks this on every request).
- Starting a new impersonation session implicitly revokes any previous one
  for the same admin, so switching targets can't leave an old token usable.
- If the session store is unreachable, validation fails closed (rejects the
  token) since impersonation is a high-privilege bypass — unlike the
  rate limiter, this must not fail open.
"""

from __future__ import annotations

import logging

from app.core.rate_limiter import get_redis_client

logger = logging.getLogger(__name__)

_KEY_PREFIX = "impersonation:active:"


def _key(admin_id: str) -> str:
    return f"{_KEY_PREFIX}{admin_id}"


async def start_impersonation_session(admin_id: str, jti: str, ttl_seconds: int) -> None:
    """Record jti as the sole active impersonation session for this admin.

    Raises on Redis failure — impersonation must not be issued if we cannot
    guarantee it will be revocable.
    """
    client = get_redis_client()
    await client.set(_key(admin_id), jti, ex=ttl_seconds)


async def end_impersonation_session(admin_id: str) -> None:
    """Best-effort revoke. Logged on failure but never raises: the admin's
    own session must still be able to end cleanly even if Redis is degraded."""
    try:
        client = get_redis_client()
        await client.delete(_key(admin_id))
    except Exception:
        logger.warning(
            "Impersonation session store unavailable while ending session for admin_id=%s",
            admin_id,
        )


async def is_impersonation_session_active(admin_id: str, jti: str) -> bool:
    try:
        client = get_redis_client()
        active_jti = await client.get(_key(admin_id))
    except Exception:
        logger.warning(
            "Impersonation session store unavailable while validating admin_id=%s; failing closed",
            admin_id,
        )
        return False
    return active_jti == jti

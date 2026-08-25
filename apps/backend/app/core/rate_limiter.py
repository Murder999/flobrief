"""Redis-backed rate limiting for auth endpoints.

Limits are shared across API instances via Redis (already provisioned through
REDIS_URL).

Fail-open vs fail-closed on a Redis outage is a deliberate, per-endpoint
choice, not an accident:

- Regular tenant login/password-reset fail OPEN (logged as a warning). This
  is defense-in-depth against brute force, not the sole line of defense
  (bcrypt cost + account lockout elsewhere), so a Redis blip must not lock
  ordinary users out entirely.
- Platform admin login and MFA verification fail CLOSED in production —
  that's the highest-privilege credential in the system, and losing rate
  limiting on it silently is not an acceptable trade for uptime. In
  non-production environments (no Redis running locally by default) they
  fail open with a loud warning instead, so local dev isn't blocked.
"""

from __future__ import annotations

import hashlib
import ipaddress
import logging

import redis.asyncio as redis
from fastapi import HTTPException, Request, status

from app.core.config import settings
from app.schemas.auth import LoginRequest, PasswordResetRequest
from app.schemas.platform import MfaRecoveryRequest, MfaVerifyRequest

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def get_redis_client() -> redis.Redis:
    """Shared Redis client accessor for other modules (e.g. impersonation
    session tracking) that need the same connection pool as the rate limiter."""
    return _get_redis()


def _strip_port(addr: str) -> str:
    addr = addr.strip()
    if addr.startswith("["):
        # Bracketed IPv6, optionally followed by :port after the bracket.
        closing = addr.find("]")
        return addr[1:closing] if closing != -1 else addr
    # A bare (unbracketed) IPv6 address has 2+ colons; only a "host:port"
    # IPv4/hostname pair has exactly one, so only strip in that case.
    if addr.count(":") == 1:
        host, _, _port = addr.rpartition(":")
        return host
    return addr


def get_client_ip(request: Request) -> str:
    """Resolve the real client IP, trusting exactly
    settings.TRUSTED_PROXY_HOP_COUNT reverse-proxy hops in front of this app
    (Railway's edge = 1 hop by default).

    X-Forwarded-For is a comma-separated chain that each hop *appends* to
    (RFC 7239 style): "client, proxy1, proxy2". We always take the entry
    exactly TRUSTED_PROXY_HOP_COUNT positions from the *right* end — never
    the leftmost/first entry, which is fully attacker-controlled. A client
    can prepend arbitrary spoofed entries to the header; that only pushes
    their own fake entries further left, it can't shift which position we
    read from the right. If fewer entries are present than the configured
    hop count (chain too short to trust), we fall back to the direct TCP
    peer rather than guessing.
    """
    direct_peer = request.client.host if request.client else "unknown"
    hops = settings.TRUSTED_PROXY_HOP_COUNT
    if hops <= 0:
        return direct_peer

    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return direct_peer

    parts = [p for p in (chunk.strip() for chunk in forwarded.split(",")) if p]
    if len(parts) < hops:
        return direct_peer

    candidate = _strip_port(parts[len(parts) - hops])
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return direct_peer
    return candidate


def _normalize_account_key(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()[:32]


async def _enforce(
    *, key: str, max_attempts: int, window_seconds: int, fail_closed: bool = False
) -> None:
    try:
        client = _get_redis()
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, window_seconds)
    except HTTPException:
        raise
    except Exception:
        logger.warning(
            "Rate limiter backend unavailable; %s for key=%s",
            "failing closed" if fail_closed else "failing open",
            key,
        )
        if fail_closed:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Servis geçici olarak kullanılamıyor. Lütfen tekrar deneyin.",
            ) from None
        return

    if count > max_attempts:
        try:
            ttl = await client.ttl(key)
        except Exception:
            ttl = window_seconds
        retry_after = max(ttl, 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Çok fazla deneme yapıldı. Lütfen daha sonra tekrar deneyin.",
            headers={"Retry-After": str(retry_after)},
        )


async def _reset(key: str) -> None:
    try:
        client = _get_redis()
        await client.delete(key)
    except Exception:
        logger.warning("Rate limiter backend unavailable while resetting key=%s", key)


# ── Tenant login / password reset ───────────────────────────────────────────
# Keyed on IP alone AND on the normalized account identifier alone (two
# independent buckets), so a single source can't hammer many accounts and a
# distributed/many-IP credential-stuffing run against one account is still
# caught even though no single IP trips the per-IP bucket.


async def rate_limit_login(request: Request, data: LoginRequest) -> None:
    ip = get_client_ip(request)
    await _enforce(
        key=f"ratelimit:login:ip:{ip}",
        max_attempts=settings.AUTH_RATE_LIMIT_ATTEMPTS,
        window_seconds=settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
    )
    await _enforce(
        key=f"ratelimit:login:acct:{_normalize_account_key(data.email)}",
        max_attempts=settings.AUTH_RATE_LIMIT_ATTEMPTS,
        window_seconds=settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
    )


async def reset_login_rate_limit(request: Request, email: str) -> None:
    """Call on successful login so a legitimate user's earlier failed
    attempts don't count against them going forward."""
    ip = get_client_ip(request)
    await _reset(f"ratelimit:login:ip:{ip}")
    await _reset(f"ratelimit:login:acct:{_normalize_account_key(email)}")


async def rate_limit_password_reset(request: Request, data: PasswordResetRequest) -> None:
    ip = get_client_ip(request)
    await _enforce(
        key=f"ratelimit:password-reset:ip:{ip}",
        max_attempts=settings.AUTH_RATE_LIMIT_ATTEMPTS,
        window_seconds=settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
    )
    await _enforce(
        key=f"ratelimit:password-reset:acct:{_normalize_account_key(data.email)}",
        max_attempts=settings.AUTH_RATE_LIMIT_ATTEMPTS,
        window_seconds=settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
    )


async def rate_limit_invitation_signup(request: Request, token: str) -> None:
    """Limit public invite onboarding without placing plaintext tokens in Redis keys."""
    ip = get_client_ip(request)
    token_digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    await _enforce(
        key=f"ratelimit:invite-signup:ip:{ip}",
        max_attempts=settings.AUTH_RATE_LIMIT_ATTEMPTS,
        window_seconds=settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
    )
    await _enforce(
        key=f"ratelimit:invite-signup:token:{token_digest}",
        max_attempts=settings.AUTH_RATE_LIMIT_ATTEMPTS,
        window_seconds=settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
    )


# ── Mention candidate search ─────────────────────────────────────────────────
# Fails open like login/password-reset: this is an authenticated, read-only,
# tenant-scoped lookup (not a credential surface), so a Redis blip must not
# block people from typing @mentions in comments.


async def rate_limit_mention_candidates(user_id: str) -> None:
    await _enforce(
        key=f"ratelimit:mentions:acct:{user_id}",
        max_attempts=60,
        window_seconds=60,
    )


# ── WhatsApp test-send (tenant + platform-admin) ────────────────────────────
# Fails open: a Redis outage should not itself become a way to bypass provider
# spend/spam limits by disabling rate limiting, but it also must not block a
# legitimate admin/owner from testing when Redis is briefly unavailable.


async def rate_limit_whatsapp_test_send(user_id: str) -> None:
    await _enforce(
        key=f"ratelimit:whatsapp-test-send:acct:{user_id}",
        max_attempts=3,
        window_seconds=600,
    )


# ── Platform admin login / MFA ──────────────────────────────────────────────
# Fail closed in production — see module docstring.


async def rate_limit_platform_login(request: Request, data: LoginRequest) -> None:
    ip = get_client_ip(request)
    fail_closed = settings.is_production
    await _enforce(
        key=f"ratelimit:platform-login:ip:{ip}",
        max_attempts=settings.PLATFORM_ADMIN_RATE_LIMIT_ATTEMPTS,
        window_seconds=settings.PLATFORM_ADMIN_RATE_LIMIT_WINDOW_SECONDS,
        fail_closed=fail_closed,
    )
    await _enforce(
        key=f"ratelimit:platform-login:acct:{_normalize_account_key(data.email)}",
        max_attempts=settings.PLATFORM_ADMIN_RATE_LIMIT_ATTEMPTS,
        window_seconds=settings.PLATFORM_ADMIN_RATE_LIMIT_WINDOW_SECONDS,
        fail_closed=fail_closed,
    )


async def reset_platform_login_rate_limit(request: Request, email: str) -> None:
    ip = get_client_ip(request)
    await _reset(f"ratelimit:platform-login:ip:{ip}")
    await _reset(f"ratelimit:platform-login:acct:{_normalize_account_key(email)}")


async def rate_limit_platform_mfa_verify(request: Request, data: MfaVerifyRequest) -> None:
    """Separate bucket from login — a TOTP brute force is a different attack
    shape (many attempts against one already-authenticated session) and must
    not share its counter with plain login attempts."""
    ip = get_client_ip(request)
    fail_closed = settings.is_production
    session_key = _normalize_account_key(data.mfa_session_token)
    await _enforce(
        key=f"ratelimit:platform-mfa-verify:ip:{ip}",
        max_attempts=settings.PLATFORM_ADMIN_MFA_RATE_LIMIT_ATTEMPTS,
        window_seconds=settings.PLATFORM_ADMIN_MFA_RATE_LIMIT_WINDOW_SECONDS,
        fail_closed=fail_closed,
    )
    await _enforce(
        key=f"ratelimit:platform-mfa-verify:session:{session_key}",
        max_attempts=settings.PLATFORM_ADMIN_MFA_RATE_LIMIT_ATTEMPTS,
        window_seconds=settings.PLATFORM_ADMIN_MFA_RATE_LIMIT_WINDOW_SECONDS,
        fail_closed=fail_closed,
    )


async def rate_limit_platform_mfa_recovery(request: Request, data: MfaRecoveryRequest) -> None:
    """Recovery codes are single-use and higher-value than a TOTP guess —
    its own bucket, separate from both login and TOTP verify."""
    ip = get_client_ip(request)
    fail_closed = settings.is_production
    session_key = _normalize_account_key(data.mfa_session_token)
    await _enforce(
        key=f"ratelimit:platform-mfa-recovery:ip:{ip}",
        max_attempts=settings.PLATFORM_ADMIN_MFA_RATE_LIMIT_ATTEMPTS,
        window_seconds=settings.PLATFORM_ADMIN_MFA_RATE_LIMIT_WINDOW_SECONDS,
        fail_closed=fail_closed,
    )
    await _enforce(
        key=f"ratelimit:platform-mfa-recovery:session:{session_key}",
        max_attempts=settings.PLATFORM_ADMIN_MFA_RATE_LIMIT_ATTEMPTS,
        window_seconds=settings.PLATFORM_ADMIN_MFA_RATE_LIMIT_WINDOW_SECONDS,
        fail_closed=fail_closed,
    )


_ALLOWLIST_DENIED = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Bu IP adresinden platform admin erişimine izin verilmiyor.",
)


def enforce_platform_ip_allowlist(request: Request) -> None:
    """If PLATFORM_ADMIN_IP_ALLOWLIST is set, reject requests from any other
    source IP. An empty allowlist (the default) leaves access unrestricted.

    Entries may be exact IPs or CIDR ranges (e.g. "10.0.0.0/24"), IPv4 or
    IPv6. A malformed entry is logged and skipped — it never widens access,
    and if every entry turns out malformed the check fails closed (denies).
    """
    raw_allowlist = [
        entry.strip() for entry in settings.PLATFORM_ADMIN_IP_ALLOWLIST.split(",") if entry.strip()
    ]
    if not raw_allowlist:
        return

    try:
        client_ip = ipaddress.ip_address(get_client_ip(request))
    except ValueError:
        raise _ALLOWLIST_DENIED from None

    for entry in raw_allowlist:
        try:
            if "/" in entry:
                if client_ip in ipaddress.ip_network(entry, strict=False):
                    return
            elif client_ip == ipaddress.ip_address(entry):
                return
        except ValueError:
            logger.warning("Invalid PLATFORM_ADMIN_IP_ALLOWLIST entry ignored: %r", entry)
            continue

    raise _ALLOWLIST_DENIED

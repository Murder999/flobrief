"""Tests for trusted-proxy-aware client IP resolution
(app/core/rate_limiter.get_client_ip, enforce_platform_ip_allowlist).

Constructs Starlette Request objects directly from a raw ASGI scope so we can
control the TCP peer address and X-Forwarded-For header independently of any
real network hop — this is what a spoofing attacker controls vs. what only a
genuine reverse proxy can set.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core.rate_limiter import enforce_platform_ip_allowlist, get_client_ip


def _make_request(*, peer: str, headers: dict[str, str] | None = None) -> Request:
    raw_headers = [
        (k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": raw_headers,
        "client": (peer, 12345),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope)


class TestGetClientIpNoProxy:
    def test_no_forwarded_header_uses_direct_peer(self) -> None:
        with patch("app.core.rate_limiter.settings") as mock_settings:
            mock_settings.TRUSTED_PROXY_HOP_COUNT = 1
            req = _make_request(peer="203.0.113.9")
            assert get_client_ip(req) == "203.0.113.9"

    def test_hop_count_zero_ignores_forwarded_header(self) -> None:
        with patch("app.core.rate_limiter.settings") as mock_settings:
            mock_settings.TRUSTED_PROXY_HOP_COUNT = 0
            req = _make_request(peer="10.0.0.5", headers={"X-Forwarded-For": "1.2.3.4"})
            assert get_client_ip(req) == "10.0.0.5"


class TestGetClientIpSingleTrustedHop:
    """TRUSTED_PROXY_HOP_COUNT=1 — Railway's edge is the only trusted hop."""

    def test_single_entry_chain_trusted(self) -> None:
        with patch("app.core.rate_limiter.settings") as mock_settings:
            mock_settings.TRUSTED_PROXY_HOP_COUNT = 1
            req = _make_request(
                peer="10.0.0.5",  # Railway's internal edge, connecting directly
                headers={"X-Forwarded-For": "198.51.100.7"},
            )
            assert get_client_ip(req) == "198.51.100.7"

    def test_spoofed_extra_entries_prepended_do_not_shift_selection(self) -> None:
        """An attacker who can only control the header value they send (not
        who connects to the proxy) can prepend fake entries, but the proxy's
        own append is always last — we read from the right, so this must not
        change which IP we pick."""
        with patch("app.core.rate_limiter.settings") as mock_settings:
            mock_settings.TRUSTED_PROXY_HOP_COUNT = 1
            genuine_client = "198.51.100.7"
            spoofed = "9.9.9.9, 8.8.8.8, 127.0.0.1"
            req = _make_request(
                peer="10.0.0.5",
                headers={"X-Forwarded-For": f"{spoofed}, {genuine_client}"},
            )
            assert get_client_ip(req) == genuine_client

    def test_direct_connection_without_proxy_header_falls_back_to_peer(self) -> None:
        with patch("app.core.rate_limiter.settings") as mock_settings:
            mock_settings.TRUSTED_PROXY_HOP_COUNT = 1
            req = _make_request(peer="6.6.6.6")
            assert get_client_ip(req) == "6.6.6.6"

    def test_chain_shorter_than_hop_count_falls_back_to_peer(self) -> None:
        with patch("app.core.rate_limiter.settings") as mock_settings:
            mock_settings.TRUSTED_PROXY_HOP_COUNT = 2
            req = _make_request(peer="10.0.0.5", headers={"X-Forwarded-For": "1.2.3.4"})
            assert get_client_ip(req) == "10.0.0.5"

    def test_malformed_entry_falls_back_to_peer(self) -> None:
        with patch("app.core.rate_limiter.settings") as mock_settings:
            mock_settings.TRUSTED_PROXY_HOP_COUNT = 1
            req = _make_request(peer="10.0.0.5", headers={"X-Forwarded-For": "not-an-ip"})
            assert get_client_ip(req) == "10.0.0.5"

    def test_ipv6_resolved(self) -> None:
        with patch("app.core.rate_limiter.settings") as mock_settings:
            mock_settings.TRUSTED_PROXY_HOP_COUNT = 1
            req = _make_request(
                peer="10.0.0.5",
                headers={"X-Forwarded-For": "2001:db8::1"},
            )
            assert get_client_ip(req) == "2001:db8::1"

    def test_ipv4_with_port_suffix_stripped(self) -> None:
        with patch("app.core.rate_limiter.settings") as mock_settings:
            mock_settings.TRUSTED_PROXY_HOP_COUNT = 1
            req = _make_request(
                peer="10.0.0.5",
                headers={"X-Forwarded-For": "198.51.100.7:54321"},
            )
            assert get_client_ip(req) == "198.51.100.7"


class TestGetClientIpMultiHop:
    def test_two_trusted_hops_picks_second_from_right(self) -> None:
        with patch("app.core.rate_limiter.settings") as mock_settings:
            mock_settings.TRUSTED_PROXY_HOP_COUNT = 2
            req = _make_request(
                peer="10.0.0.5",
                headers={"X-Forwarded-For": "198.51.100.7, 10.0.0.9"},
            )
            assert get_client_ip(req) == "198.51.100.7"


class TestEnforcePlatformIpAllowlist:
    def test_empty_allowlist_allows_everything(self) -> None:
        with patch("app.core.rate_limiter.settings") as mock_settings:
            mock_settings.PLATFORM_ADMIN_IP_ALLOWLIST = ""
            mock_settings.TRUSTED_PROXY_HOP_COUNT = 1
            req = _make_request(peer="1.2.3.4")
            enforce_platform_ip_allowlist(req)  # must not raise

    def test_exact_ip_match_allowed(self) -> None:
        with patch("app.core.rate_limiter.settings") as mock_settings:
            mock_settings.PLATFORM_ADMIN_IP_ALLOWLIST = "203.0.113.9"
            mock_settings.TRUSTED_PROXY_HOP_COUNT = 1
            req = _make_request(peer="203.0.113.9")
            enforce_platform_ip_allowlist(req)  # must not raise

    def test_non_matching_ip_denied(self) -> None:
        with patch("app.core.rate_limiter.settings") as mock_settings:
            mock_settings.PLATFORM_ADMIN_IP_ALLOWLIST = "203.0.113.9"
            mock_settings.TRUSTED_PROXY_HOP_COUNT = 1
            req = _make_request(peer="6.6.6.6")
            with pytest.raises(HTTPException) as exc_info:
                enforce_platform_ip_allowlist(req)
            assert exc_info.value.status_code == 403

    def test_cidr_range_match_allowed(self) -> None:
        with patch("app.core.rate_limiter.settings") as mock_settings:
            mock_settings.PLATFORM_ADMIN_IP_ALLOWLIST = "10.0.0.0/24"
            mock_settings.TRUSTED_PROXY_HOP_COUNT = 1
            req = _make_request(peer="10.0.0.42")
            enforce_platform_ip_allowlist(req)  # must not raise

    def test_cidr_range_outside_denied(self) -> None:
        with patch("app.core.rate_limiter.settings") as mock_settings:
            mock_settings.PLATFORM_ADMIN_IP_ALLOWLIST = "10.0.0.0/24"
            mock_settings.TRUSTED_PROXY_HOP_COUNT = 1
            req = _make_request(peer="10.0.1.42")
            with pytest.raises(HTTPException):
                enforce_platform_ip_allowlist(req)

    def test_malformed_entry_does_not_silently_open_access(self) -> None:
        """A garbage allowlist entry must be skipped (logged), never treated
        as a wildcard that lets everything through."""
        with patch("app.core.rate_limiter.settings") as mock_settings:
            mock_settings.PLATFORM_ADMIN_IP_ALLOWLIST = "not-a-valid-entry"
            mock_settings.TRUSTED_PROXY_HOP_COUNT = 1
            req = _make_request(peer="6.6.6.6")
            with pytest.raises(HTTPException) as exc_info:
                enforce_platform_ip_allowlist(req)
            assert exc_info.value.status_code == 403

    def test_extra_spoofed_entries_do_not_help_attacker_pass_allowlist(self) -> None:
        """An attacker who reaches the real proxy and forges extra entries
        in X-Forwarded-For can't shift which entry we trust (we always read
        from the right by hop count) to smuggle an allowlisted IP through."""
        with patch("app.core.rate_limiter.settings") as mock_settings:
            mock_settings.PLATFORM_ADMIN_IP_ALLOWLIST = "203.0.113.9"
            mock_settings.TRUSTED_PROXY_HOP_COUNT = 1
            req = _make_request(
                peer="10.0.0.5",  # the real proxy
                headers={"X-Forwarded-For": "203.0.113.9, 6.6.6.6"},
            )
            with pytest.raises(HTTPException):
                enforce_platform_ip_allowlist(req)

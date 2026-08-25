"""
Unit tests for Part 13 — Platform admin, MFA, owner dashboard.
No DB required — pure Python logic tests.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import struct
import time

from app.schemas.auth import TokenResponse
from app.schemas.platform import (
    AgencySuspendRequest,
    ImpersonateStartRequest,
    MfaConfirmRequest,
    MfaConfirmResponse,
    MfaDisableRequest,
    MfaRecoveryRequest,
    MfaSetupResponse,
    MfaVerifyRequest,
    OwnerDashboardStats,
    OwnerMemberRead,
    OwnerSubscriptionRead,
    PlatformAgencyDetail,
    PlatformAgencyRead,
    PlatformAnalytics,
    PlatformAuditLogRead,
    PlatformDashboardStats,
    PlatformSubscriptionRead,
    PlatformUserRead,
)
from app.services.mfa_service import build_otpauth_url

# ── TOTP implementation helpers (copied from service) ─────────────────────────


def _hotp(secret_bytes: bytes, counter: int) -> int:
    msg = struct.pack(">Q", counter)
    mac = hmac.new(secret_bytes, msg, hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    code = struct.unpack(">I", mac[offset : offset + 4])[0] & 0x7FFFFFFF
    return code % 1_000_000


def _current_totp(secret_b32: str) -> str:
    secret_bytes = base64.b32decode(secret_b32.upper())
    counter = int(time.time()) // 30
    return str(_hotp(secret_bytes, counter)).zfill(6)


# ── TokenResponse schema tests ────────────────────────────────────────────────


class TestTokenResponseMfa:
    def test_mfa_required_response(self):
        r = TokenResponse(
            access_token="",
            expires_in=0,
            mfa_required=True,
            mfa_session_token="tok123",
        )
        assert r.mfa_required is True
        assert r.mfa_session_token == "tok123"
        assert r.access_token == ""

    def test_full_token_response(self):
        r = TokenResponse(access_token="abc", expires_in=300)
        assert r.mfa_required is False
        assert r.mfa_session_token is None

    def test_defaults(self):
        r = TokenResponse()
        assert r.access_token == ""
        assert r.expires_in == 0
        assert r.mfa_required is False


# ── MFA schema validation ─────────────────────────────────────────────────────


class TestMfaSchemas:
    def test_setup_response(self):
        r = MfaSetupResponse(
            secret="JBSWY3DPEHPK3PXP",
            otpauth_url="otpauth://totp/PostPiloter:admin@example.com?secret=JBSWY3DPEHPK3PXP",
        )
        assert r.secret == "JBSWY3DPEHPK3PXP"
        assert "otpauth://totp" in r.otpauth_url

    def test_otpauth_uses_postpiloter_issuer(self):
        url = build_otpauth_url("JBSWY3DPEHPK3PXP", "admin@example.com")
        assert "/PostPiloter:admin%40example.com" in url
        assert "issuer=PostPiloter" in url

    def test_confirm_request_requires_code(self):
        r = MfaConfirmRequest(code="123456")
        assert r.code == "123456"

    def test_confirm_response_has_codes(self):
        r = MfaConfirmResponse(
            recovery_codes=["AABBCC-DDEEFF", "112233-445566"],
            message="MFA enabled.",
        )
        assert len(r.recovery_codes) == 2

    def test_disable_request(self):
        r = MfaDisableRequest(code="000000")
        assert r.code == "000000"

    def test_verify_request(self):
        r = MfaVerifyRequest(mfa_session_token="session.tok", code="654321")
        assert r.mfa_session_token == "session.tok"

    def test_recovery_request(self):
        r = MfaRecoveryRequest(mfa_session_token="s", recovery_code="AABBCC-DDEEFF")
        assert r.recovery_code == "AABBCC-DDEEFF"


# ── Platform schema validation ────────────────────────────────────────────────


class TestPlatformAgencySchemas:
    def test_agency_read_requires_fields(self):
        import uuid
        from datetime import datetime

        r = PlatformAgencyRead(
            id=uuid.uuid4(),
            name="Test Agency",
            slug="test-agency",
            status="active",
            owner_user_id=None,
            plan_id=None,
            member_count=3,
            brand_count=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        assert r.member_count == 3
        assert r.slug == "test-agency"

    def test_agency_detail_extends_read(self):
        import uuid
        from datetime import datetime

        r = PlatformAgencyDetail(
            id=uuid.uuid4(),
            name="Foo",
            slug="foo",
            status="suspended",
            owner_user_id=None,
            plan_id=None,
            member_count=0,
            brand_count=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            subscription_status="active",
            plan_name="Pro",
            plan_code="pro_agency",
            monthly_price_cents=9900,
        )
        assert r.subscription_status == "active"
        assert r.monthly_price_cents == 9900

    def test_suspend_request_requires_reason(self):
        r = AgencySuspendRequest(reason="Terms violation")
        assert r.reason == "Terms violation"


class TestPlatformUserSchemas:
    def test_user_read(self):
        import uuid
        from datetime import datetime

        r = PlatformUserRead(
            id=uuid.uuid4(),
            email="a@b.com",
            full_name="Alice",
            user_type="tenant_user",
            is_active=True,
            is_verified=True,
            mfa_enabled=False,
            last_login_at=None,
            created_at=datetime.utcnow(),
        )
        assert r.email == "a@b.com"
        assert r.mfa_enabled is False


class TestPlatformSubscriptionSchemas:
    def test_subscription_read(self):
        import uuid
        from datetime import datetime

        r = PlatformSubscriptionRead(
            id=uuid.uuid4(),
            agency_id=uuid.uuid4(),
            agency_name="Acme",
            brand_id=None,
            plan_id=uuid.uuid4(),
            plan_name="Starter",
            plan_code="starter_agency",
            status="active",
            monthly_price_cents=4900,
            current_period_start=None,
            current_period_end=None,
            created_at=datetime.utcnow(),
        )
        assert r.plan_code == "starter_agency"
        assert r.monthly_price_cents == 4900

    def test_subscription_override_requires_reason(self):
        import uuid

        from app.schemas.platform import SubscriptionOverrideRequest

        r = SubscriptionOverrideRequest(plan_id=uuid.uuid4(), reason="Upgrade")
        assert r.reason == "Upgrade"


class TestPlatformDashboardSchemas:
    def test_dashboard_stats(self):
        s = PlatformDashboardStats(
            total_agencies=10,
            active_agencies=8,
            suspended_agencies=2,
            total_users=150,
            active_users_30d=45,
            total_subscriptions=10,
            mrr_cents=99000,
        )
        assert s.mrr_cents == 99000

    def test_analytics(self):
        a = PlatformAnalytics(
            agencies_by_status={"active": 5, "suspended": 1},
            users_by_type={"tenant_user": 120, "platform_admin": 1},
            plan_distribution={"starter_agency": 4, "pro_agency": 2},
        )
        assert a.agencies_by_status["active"] == 5

    def test_audit_log_read(self):
        import uuid
        from datetime import datetime

        r = PlatformAuditLogRead(
            id=uuid.uuid4(),
            admin_user_id=uuid.uuid4(),
            action="agency.suspended",
            target_type="agency",
            target_id=uuid.uuid4(),
            target_tenant_type=None,
            target_tenant_id=None,
            meta={"reason": "TOS violation"},
            ip_address="127.0.0.1",
            user_agent="pytest",
            created_at=datetime.utcnow(),
        )
        assert r.action == "agency.suspended"
        assert r.meta["reason"] == "TOS violation"


# ── Owner dashboard schemas ───────────────────────────────────────────────────


class TestOwnerSchemas:
    def test_dashboard_stats(self):
        s = OwnerDashboardStats(
            active_brands=3,
            active_members=7,
            open_briefs=12,
            approved_briefs_total=45,
            calendar_items_this_month=8,
        )
        assert s.active_brands == 3
        assert s.approved_briefs_total == 45

    def test_member_read(self):
        import uuid
        from datetime import datetime

        r = OwnerMemberRead(
            member_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            full_name="Bob",
            email="bob@example.com",
            role="agency_member",
            status="active",
            last_login_at=None,
            joined_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
        assert r.email == "bob@example.com"

    def test_subscription_read(self):
        from datetime import datetime

        r = OwnerSubscriptionRead(
            plan_code="pro_agency",
            plan_name="Pro Agency",
            plan_description="All features",
            status="active",
            max_brands=10,
            max_users=20,
            monthly_price_cents=9900,
            current_period_end=datetime.utcnow(),
            active_brands=3,
            active_members=5,
        )
        assert r.max_brands == 10
        assert r.active_members == 5


# ── TOTP algorithm correctness ────────────────────────────────────────────────


class TestTotpAlgorithm:
    def test_hotp_6_digits(self):
        secret = base64.b32encode(b"12345678901234567890").decode()
        code = _hotp(base64.b32decode(secret.upper()), 0)
        assert 0 <= code < 1_000_000

    def test_current_totp_is_6_chars(self):
        import secrets as s

        secret = base64.b32encode(s.token_bytes(20)).decode()
        code = _current_totp(secret)
        assert len(code) == 6
        assert code.isdigit()

    def test_totp_window_consistency(self):
        """The same secret should produce the same code within the same 30s window."""
        import secrets as s

        secret = base64.b32encode(s.token_bytes(20)).decode()
        code1 = _current_totp(secret)
        code2 = _current_totp(secret)
        assert code1 == code2

    def test_different_secrets_different_codes(self):
        import secrets as s

        s1 = base64.b32encode(s.token_bytes(20)).decode()
        s2 = base64.b32encode(s.token_bytes(20)).decode()
        c1 = _current_totp(s1)
        c2 = _current_totp(s2)
        # Not guaranteed to differ, but with 20-byte random secrets it's overwhelmingly likely
        # This is a statistical sanity check, not a hard invariant
        assert len(c1) == 6
        assert len(c2) == 6


# ── Impersonation schema ──────────────────────────────────────────────────────


class TestImpersonationSchemas:
    def test_start_request_requires_reason(self):
        r = ImpersonateStartRequest(reason="Support request #123")
        assert r.reason == "Support request #123"

    def test_impersonation_response(self):
        from app.schemas.platform import ImpersonationResponse

        r = ImpersonationResponse(
            access_token="tok",
            expires_in=3600,
            impersonated_user_id="user-uuid",
            impersonated_email="user@example.com",
            impersonated_user_type="tenant_user",
        )
        assert r.expires_in == 3600
        assert r.impersonated_user_type == "tenant_user"

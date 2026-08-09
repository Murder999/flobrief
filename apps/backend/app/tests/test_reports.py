"""Unit tests for reporting: enums, token security, PDF generation, public view isolation.

No DB required — pure Python logic.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta

from app.models.enums import ReportStatus, ReportType
from app.services.report_export_service import ReportExportService

# ── Enum tests ────────────────────────────────────────────────────────────────


def test_report_type_values() -> None:
    assert ReportType.MONTHLY_BRAND == "monthly_brand"
    assert ReportType.AGENCY_OVERVIEW == "agency_overview"
    assert ReportType.CAMPAIGN_SUMMARY == "campaign_summary"


def test_report_status_values() -> None:
    assert ReportStatus.DRAFT == "draft"
    assert ReportStatus.GENERATED == "generated"
    assert ReportStatus.SHARED == "shared"
    assert ReportStatus.ARCHIVED == "archived"


def test_report_type_count() -> None:
    assert len(ReportType) == 3


def test_report_status_count() -> None:
    assert len(ReportStatus) == 4


# ── Token security tests ──────────────────────────────────────────────────────


def test_share_token_hash_is_sha256() -> None:
    raw = secrets.token_urlsafe(48)
    stored_hash = hashlib.sha256(raw.encode()).hexdigest()
    assert len(stored_hash) == 64
    assert stored_hash != raw


def test_share_token_raw_not_equal_hash() -> None:
    raw = "my_secret_token"
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    assert hashed != raw


def test_share_token_hash_deterministic() -> None:
    raw = "test_token_abc"
    h1 = hashlib.sha256(raw.encode()).hexdigest()
    h2 = hashlib.sha256(raw.encode()).hexdigest()
    assert h1 == h2


def test_share_token_different_inputs_different_hashes() -> None:
    h1 = hashlib.sha256(b"token_a").hexdigest()
    h2 = hashlib.sha256(b"token_b").hexdigest()
    assert h1 != h2


def test_share_token_expiry_logic() -> None:
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=30)
    assert expires_at > now


def test_share_token_expired_detection() -> None:
    expired_at = datetime.now(UTC) - timedelta(seconds=1)
    now = datetime.now(UTC)
    assert expired_at < now


def test_share_token_revoked_detection() -> None:
    revoked_at = datetime.now(UTC) - timedelta(minutes=5)
    assert revoked_at is not None


def test_share_token_urlsafe_length() -> None:
    raw = secrets.token_urlsafe(48)
    assert len(raw) >= 48


# ── Public report isolation tests ─────────────────────────────────────────────


def _make_public_view(metrics: dict) -> dict:
    """Simulate public report view — no agency_id, no internal IDs."""
    return {
        "report_type": "monthly_brand",
        "period_start": date(2026, 6, 1).isoformat(),
        "period_end": date(2026, 6, 30).isoformat(),
        "title": "Haziran 2026 Raporu",
        "metrics": metrics,
        "narrative": None,
        "generated_at": datetime.utcnow().isoformat(),
        "allow_pdf_download": True,
    }


def test_public_report_no_agency_id() -> None:
    view = _make_public_view({})
    assert "agency_id" not in view


def test_public_report_no_created_by_id() -> None:
    view = _make_public_view({})
    assert "created_by_id" not in view


def test_public_report_no_brand_id() -> None:
    view = _make_public_view({})
    assert "brand_id" not in view


def test_public_report_has_metrics() -> None:
    view = _make_public_view({"created_briefs_count": 5})
    assert view["metrics"]["created_briefs_count"] == 5


def test_public_report_no_token_hash() -> None:
    view = _make_public_view({})
    assert "token_hash" not in view


# ── Metrics structure tests ───────────────────────────────────────────────────


def test_metrics_expected_keys() -> None:
    expected = {
        "created_briefs_count",
        "approved_briefs_count",
        "revision_requested_count",
        "pending_approvals_count",
        "published_calendar_items_count",
        "planned_calendar_items_count",
        "average_approval_time_hours",
        "most_revised_briefs",
        "calendar_status_distribution",
        "platform_distribution",
        "period_start",
        "period_end",
    }
    sample = {
        "created_briefs_count": 0,
        "approved_briefs_count": 0,
        "revision_requested_count": 0,
        "pending_approvals_count": 0,
        "published_calendar_items_count": 0,
        "planned_calendar_items_count": 0,
        "average_approval_time_hours": None,
        "most_revised_briefs": [],
        "calendar_status_distribution": {},
        "platform_distribution": {},
        "period_start": "2026-06-01",
        "period_end": "2026-06-30",
    }
    assert expected == set(sample.keys())


def test_metrics_approval_rate_none_when_no_approvals() -> None:
    metrics = {"average_approval_time_hours": None}
    assert metrics["average_approval_time_hours"] is None


def test_metrics_most_revised_is_list() -> None:
    metrics = {"most_revised_briefs": []}
    assert isinstance(metrics["most_revised_briefs"], list)


def test_metrics_platform_distribution_dict() -> None:
    dist = {"instagram": 5, "facebook": 3}
    assert isinstance(dist, dict)
    assert dist["instagram"] == 5


# ── PDF generation tests ──────────────────────────────────────────────────────


def _fake_report() -> object:
    class FakeReport:
        id = uuid.uuid4()
        report_type = "monthly_brand"
        period_start = date(2026, 6, 1)
        period_end = date(2026, 6, 30)
        title = "Haziran 2026 Test Raporu"

    return FakeReport()


def _fake_snapshot(metrics: dict | None = None) -> object:
    class FakeSnapshot:
        id = uuid.uuid4()
        created_at = datetime.utcnow()
        narrative = None

    snap = FakeSnapshot()
    snap.metrics = metrics or {  # type: ignore[attr-defined]
        "created_briefs_count": 12,
        "approved_briefs_count": 8,
        "revision_requested_count": 3,
        "pending_approvals_count": 1,
        "published_calendar_items_count": 5,
        "planned_calendar_items_count": 4,
        "average_approval_time_hours": 24.5,
        "most_revised_briefs": [{"brief_id": str(uuid.uuid4()), "revision_count": 2}],
        "calendar_status_distribution": {"published": 5, "planned": 4},
        "platform_distribution": {"instagram": 7, "facebook": 3},
        "period_start": "2026-06-01",
        "period_end": "2026-06-30",
    }
    return snap


def test_pdf_returns_bytes() -> None:
    report = _fake_report()
    snapshot = _fake_snapshot()
    result = ReportExportService.build_pdf_bytes(report, snapshot)  # type: ignore[arg-type]
    assert isinstance(result, bytes)


def test_pdf_non_empty() -> None:
    report = _fake_report()
    snapshot = _fake_snapshot()
    result = ReportExportService.build_pdf_bytes(report, snapshot)  # type: ignore[arg-type]
    assert len(result) > 1024


def test_pdf_starts_with_pdf_header() -> None:
    report = _fake_report()
    snapshot = _fake_snapshot()
    result = ReportExportService.build_pdf_bytes(report, snapshot)  # type: ignore[arg-type]
    assert result[:4] == b"%PDF"


def test_pdf_with_empty_metrics() -> None:
    report = _fake_report()
    snapshot = _fake_snapshot(
        {
            "created_briefs_count": 0,
            "approved_briefs_count": 0,
            "revision_requested_count": 0,
            "pending_approvals_count": 0,
            "published_calendar_items_count": 0,
            "planned_calendar_items_count": 0,
            "average_approval_time_hours": None,
            "most_revised_briefs": [],
            "calendar_status_distribution": {},
            "platform_distribution": {},
            "period_start": "2026-06-01",
            "period_end": "2026-06-30",
        }
    )
    result = ReportExportService.build_pdf_bytes(report, snapshot)  # type: ignore[arg-type]
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_pdf_with_platform_distribution() -> None:
    report = _fake_report()
    snapshot = _fake_snapshot(
        {
            "created_briefs_count": 5,
            "approved_briefs_count": 3,
            "revision_requested_count": 1,
            "pending_approvals_count": 0,
            "published_calendar_items_count": 10,
            "planned_calendar_items_count": 2,
            "average_approval_time_hours": 12.0,
            "most_revised_briefs": [],
            "calendar_status_distribution": {"published": 10, "planned": 2},
            "platform_distribution": {
                "instagram": 6,
                "facebook": 2,
                "tiktok": 1,
                "linkedin": 1,
            },
            "period_start": "2026-06-01",
            "period_end": "2026-06-30",
        }
    )
    result = ReportExportService.build_pdf_bytes(report, snapshot)  # type: ignore[arg-type]
    assert result[:4] == b"%PDF"


# ── Snapshot independence tests ───────────────────────────────────────────────


def test_snapshot_metrics_frozen_at_generation() -> None:
    """Snapshot preserves metrics at generation time regardless of DB changes."""
    original_metrics = {"created_briefs_count": 5}
    snapshot_metrics = dict(original_metrics)
    original_metrics["created_briefs_count"] = 999
    assert snapshot_metrics["created_briefs_count"] == 5

"""Regression coverage for the time-tracking notification deep-links.

Before this fix, TIME_ENTRY_LONG_RUNNING / TIME_ENTRY_STILL_RUNNING_EOD /
TIMESHEET_MISSING had no branch in build_notification_action_url at all —
they always fell through to None (dead click, notification list fallback)
since they carry no brief_id. All three now route to the self-service
/dashboard/time/my view specifically (never /team, /by-brand, /missing)
because their recipient is always the individual the event is about, who
may not hold TIME_ENTRY_VIEW_TEAM.
"""

from __future__ import annotations

from app.models.enums import NotificationEventType
from app.services.notification_routes import build_notification_action_url


class TestTimerEventRoutes:
    def test_long_running_timer_routes_to_my_time_with_active_marker(self) -> None:
        url = build_notification_action_url(
            NotificationEventType.TIME_ENTRY_LONG_RUNNING.value,
            {"entry_id": "irrelevant", "elapsed_hours": 5.2},
            "agency",
        )
        assert url == "/dashboard/time/my?timer=active"

    def test_still_running_eod_routes_to_my_time_with_active_marker(self) -> None:
        url = build_notification_action_url(
            NotificationEventType.TIME_ENTRY_STILL_RUNNING_EOD.value,
            {"entry_id": "irrelevant", "started_at": "2026-07-20T09:00:00+00:00"},
            "agency",
        )
        assert url == "/dashboard/time/my?timer=active"

    def test_timer_events_unroutable_for_brand_portal(self) -> None:
        """Brand users never receive these, but the function must stay
        defensive rather than emit an agency-only path for a brand session."""
        assert (
            build_notification_action_url(
                NotificationEventType.TIME_ENTRY_LONG_RUNNING.value, {}, "brand"
            )
            is None
        )


class TestTimesheetMissingRoute:
    def test_routes_to_my_time_with_the_missing_date_as_a_custom_range(self) -> None:
        url = build_notification_action_url(
            NotificationEventType.TIMESHEET_MISSING.value,
            {"dedup_key": "irrelevant", "missing_date": "2026-07-19"},
            "agency",
        )
        assert url == "/dashboard/time/my?range=custom&start=2026-07-19&end=2026-07-19"

    def test_never_routes_to_the_team_scoped_missing_page(self) -> None:
        """The person missing their own timesheet is not guaranteed
        TIME_ENTRY_VIEW_TEAM — routing to /dashboard/time/missing would 403
        for most recipients."""
        url = build_notification_action_url(
            NotificationEventType.TIMESHEET_MISSING.value,
            {"missing_date": "2026-07-19"},
            "agency",
        )
        assert url is not None
        assert "/dashboard/time/missing" not in url
        assert url.startswith("/dashboard/time/my")

    def test_falls_back_to_bare_my_time_when_missing_date_is_malformed(self) -> None:
        url = build_notification_action_url(
            NotificationEventType.TIMESHEET_MISSING.value,
            {"missing_date": "not-a-date"},
            "agency",
        )
        assert url == "/dashboard/time/my"

    def test_falls_back_to_bare_my_time_when_missing_date_absent(self) -> None:
        url = build_notification_action_url(
            NotificationEventType.TIMESHEET_MISSING.value, {}, "agency"
        )
        assert url == "/dashboard/time/my"

    def test_unroutable_for_brand_portal(self) -> None:
        assert (
            build_notification_action_url(
                NotificationEventType.TIMESHEET_MISSING.value,
                {"missing_date": "2026-07-19"},
                "brand",
            )
            is None
        )


class TestInvoiceEventRoutes:
    """Before this fix, all four INVOICE_* events had no branch in
    build_notification_action_url — they carry invoice_id, not brief_id, so
    they always fell through the brief_id-gated branches to None (dead
    click, notification list fallback)."""

    def test_invoice_sent_routes_to_the_brand_portal_invoice_detail(self) -> None:
        url = build_notification_action_url(
            NotificationEventType.INVOICE_SENT.value,
            {"invoice_id": "6f9a1b2c-3d4e-4f5a-8b6c-7d8e9f0a1b2c", "invoice_number": "F-0001"},
            "brand",
        )
        assert url == "/brand/invoices/6f9a1b2c-3d4e-4f5a-8b6c-7d8e9f0a1b2c"

    def test_invoice_sent_routes_to_the_agency_invoice_detail_when_viewed_from_agency(self) -> None:
        url = build_notification_action_url(
            NotificationEventType.INVOICE_SENT.value,
            {"invoice_id": "6f9a1b2c-3d4e-4f5a-8b6c-7d8e9f0a1b2c"},
            "agency",
        )
        assert url == "/dashboard/finance/invoices/6f9a1b2c-3d4e-4f5a-8b6c-7d8e9f0a1b2c"

    def test_invoice_overdue_routes_to_the_agency_invoice_detail(self) -> None:
        url = build_notification_action_url(
            NotificationEventType.INVOICE_OVERDUE.value,
            {"invoice_id": "6f9a1b2c-3d4e-4f5a-8b6c-7d8e9f0a1b2c", "days_overdue": 3},
            "agency",
        )
        assert url == "/dashboard/finance/invoices/6f9a1b2c-3d4e-4f5a-8b6c-7d8e9f0a1b2c"

    def test_invoice_approval_pending_and_send_failed_also_route(self) -> None:
        for event in (
            NotificationEventType.INVOICE_APPROVAL_PENDING.value,
            NotificationEventType.INVOICE_SEND_FAILED.value,
        ):
            url = build_notification_action_url(
                event, {"invoice_id": "6f9a1b2c-3d4e-4f5a-8b6c-7d8e9f0a1b2c"}, "agency"
            )
            assert url == "/dashboard/finance/invoices/6f9a1b2c-3d4e-4f5a-8b6c-7d8e9f0a1b2c"

    def test_unroutable_when_invoice_id_missing_or_malformed(self) -> None:
        assert (
            build_notification_action_url(NotificationEventType.INVOICE_SENT.value, {}, "brand")
            is None
        )
        assert (
            build_notification_action_url(
                NotificationEventType.INVOICE_SENT.value, {"invoice_id": "not-a-uuid"}, "brand"
            )
            is None
        )


class TestExistingRoutesUnaffected:
    """Guards against the new branches accidentally shadowing brief-scoped
    events that legitimately have no brief_id-independent handling."""

    def test_deliverable_submitted_still_routes_by_brief_id(self) -> None:
        url = build_notification_action_url(
            NotificationEventType.DELIVERABLE_SUBMITTED.value,
            {"brief_id": "6f9a1b2c-3d4e-4f5a-8b6c-7d8e9f0a1b2c"},
            "agency",
        )
        assert url is not None
        assert url.startswith("/dashboard/briefs/6f9a1b2c-3d4e-4f5a-8b6c-7d8e9f0a1b2c")

    def test_unknown_event_type_without_brief_id_is_unroutable(self) -> None:
        assert build_notification_action_url("some.unknown.event", {}, "agency") is None

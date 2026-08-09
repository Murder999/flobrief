"""Unit tests for the WhatsApp delivery state machine (Part 6B-3).

Pure-function tests — no DB, no event loop — against
app.services.whatsapp_delivery_state_machine.apply_transition.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.enums import NotificationDeliveryStatus as S
from app.models.notification import NotificationDelivery
from app.services.whatsapp_delivery_state_machine import apply_transition, is_terminal, rank

NOW = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)


def _delivery(status: str) -> NotificationDelivery:
    d = NotificationDelivery(channel="whatsapp", status=status, provider="twilio_production")
    return d


class TestGoldenPath:
    def test_queued_to_accepted_to_sent_to_delivered_to_read(self) -> None:
        d = _delivery(S.QUEUED.value)
        d.queued_at = NOW

        r1 = apply_transition(d, S.ACCEPTED.value, now=NOW)
        assert r1.applied is True
        assert d.status == S.ACCEPTED.value
        assert d.accepted_at == NOW

        r2 = apply_transition(d, S.SENT.value, now=NOW)
        assert r2.applied is True
        assert d.sent_at == NOW

        r3 = apply_transition(d, S.DELIVERED.value, now=NOW)
        assert r3.applied is True
        assert d.delivered_at == NOW

        r4 = apply_transition(d, S.READ.value, now=NOW)
        assert r4.applied is True
        assert d.read_at == NOW
        assert is_terminal(d.status) is True

    def test_sent_can_skip_directly_to_read(self) -> None:
        """Twilio can skip the `delivered` callback in practice — the state
        machine only requires forward progress, not every intermediate step."""
        d = _delivery(S.SENT.value)
        r = apply_transition(d, S.READ.value, now=NOW)
        assert r.applied is True
        assert d.status == S.READ.value


class TestDuplicateCallback:
    def test_same_status_twice_is_a_noop(self) -> None:
        d = _delivery(S.DELIVERED.value)
        d.delivered_at = NOW
        earlier = NOW
        r = apply_transition(d, S.DELIVERED.value, now=datetime(2026, 7, 29, 13, 0, tzinfo=UTC))
        assert r.applied is False
        assert r.reason == "duplicate"
        assert d.delivered_at == earlier  # never overwritten

    def test_duplicate_terminal_failed_is_a_noop(self) -> None:
        d = _delivery(S.FAILED.value)
        d.failed_at = NOW
        r = apply_transition(d, S.FAILED.value, now=NOW)
        assert r.applied is False


class TestOutOfOrderAndRegression:
    def test_read_then_delivered_is_rejected(self) -> None:
        d = _delivery(S.READ.value)
        r = apply_transition(d, S.DELIVERED.value, now=NOW)
        assert r.applied is False
        assert d.status == S.READ.value

    def test_read_then_sent_is_rejected(self) -> None:
        d = _delivery(S.READ.value)
        r = apply_transition(d, S.SENT.value, now=NOW)
        assert r.applied is False
        assert d.status == S.READ.value

    def test_delivered_then_sent_is_rejected(self) -> None:
        d = _delivery(S.DELIVERED.value)
        r = apply_transition(d, S.SENT.value, now=NOW)
        assert r.applied is False
        assert d.status == S.DELIVERED.value

    def test_delivered_then_queued_is_rejected(self) -> None:
        d = _delivery(S.DELIVERED.value)
        r = apply_transition(d, S.QUEUED.value, now=NOW)
        assert r.applied is False
        assert d.status == S.DELIVERED.value

    def test_sent_then_accepted_is_rejected(self) -> None:
        d = _delivery(S.SENT.value)
        r = apply_transition(d, S.ACCEPTED.value, now=NOW)
        assert r.applied is False
        assert d.status == S.SENT.value
        assert r.reason == "regression_or_out_of_order"

    def test_out_of_order_never_overwrites_existing_timestamp(self) -> None:
        d = _delivery(S.DELIVERED.value)
        d.delivered_at = NOW
        later = datetime(2026, 7, 29, 13, 0, tzinfo=UTC)
        apply_transition(d, S.SENT.value, now=later)
        assert d.delivered_at == NOW
        assert d.sent_at is None


class TestTerminalStates:
    def test_failed_reachable_from_any_progress_state(self) -> None:
        starts = (
            S.PROCESSING.value,
            S.PENDING.value,
            S.QUEUED.value,
            S.ACCEPTED.value,
            S.SENT.value,
        )
        for start in starts:
            d = _delivery(start)
            r = apply_transition(d, S.FAILED.value, now=NOW)
            assert r.applied is True, f"expected FAILED reachable from {start}"
            assert d.status == S.FAILED.value

    def test_no_transition_leaves_a_terminal_skip_status(self) -> None:
        d = _delivery(S.SKIPPED_NO_CONSENT.value)
        r = apply_transition(d, S.SENT.value, now=NOW)
        assert r.applied is False
        assert r.reason == "already_terminal"
        assert d.status == S.SKIPPED_NO_CONSENT.value

    def test_cancelled_and_expired_are_terminal(self) -> None:
        for terminal_status in (S.CANCELLED.value, S.EXPIRED.value):
            d = _delivery(terminal_status)
            r = apply_transition(d, S.SENT.value, now=NOW)
            assert r.applied is False


class TestFailureMetadata:
    def test_failed_transition_records_error_and_category(self) -> None:
        d = _delivery(S.SENT.value)
        r = apply_transition(
            d,
            S.FAILED.value,
            now=NOW,
            error_message="Twilio callback error 30008: undelivered",
            failure_category="provider_reported_failure",
        )
        assert r.applied is True
        assert d.error_message == "Twilio callback error 30008: undelivered"
        assert d.failure_category == "provider_reported_failure"


class TestRankAndTerminalHelpers:
    def test_rank_ordering_is_strictly_increasing_along_golden_path(self) -> None:
        path = [
            S.PROCESSING.value,
            S.PENDING.value,
            S.QUEUED.value,
            S.ACCEPTED.value,
            S.SENT.value,
            S.DELIVERED.value,
            S.READ.value,
        ]
        ranks = [rank(s) for s in path]
        assert ranks == sorted(ranks)
        assert len(set(ranks)) == len(ranks)

    def test_unknown_status_has_no_rank(self) -> None:
        assert rank("not_a_real_status") is None

    def test_is_terminal_true_for_every_skip_status(self) -> None:
        statuses = (
            S.SKIPPED.value,
            S.SKIPPED_ROLE.value,
            S.SKIPPED_DISABLED.value,
            S.SKIPPED_NO_CONSENT.value,
            S.SKIPPED_NO_PHONE.value,
            S.SKIPPED_UNVERIFIED_PHONE.value,
            S.SKIPPED_TEMPLATE_MISSING.value,
            S.SKIPPED_DEMO_TENANT.value,
            S.SKIPPED_EVENT_DISABLED.value,
            S.NOT_CONFIGURED.value,
            S.PASSIVE.value,
            S.FAILED.value,
            S.CANCELLED.value,
            S.EXPIRED.value,
            S.READ.value,
        )
        for status in statuses:
            assert is_terminal(status) is True

    def test_is_terminal_false_for_progress_states(self) -> None:
        statuses = (
            S.PROCESSING.value,
            S.PENDING.value,
            S.QUEUED.value,
            S.ACCEPTED.value,
            S.SENT.value,
            S.DELIVERED.value,
        )
        for status in statuses:
            assert is_terminal(status) is False

"""Single source of truth for "today"/"now" in application logic.

Every persisted timestamp in this codebase (TimeEntry.started_at, etc.) is
UTC-anchored (see Part 1 conventions). Computing "today" from the local
system clock (`date.today()`, `datetime.now()` without a timezone) silently
diverges from that near local midnight whenever the server's system
timezone isn't UTC — e.g. a server running in `Europe/Istanbul` (UTC+3) has
a ~3-hour daily window (00:00-03:00 local) where the local calendar date is
already "tomorrow" relative to the UTC day boundaries used everywhere else,
causing date-range/report logic to miscompute. Always use these helpers
instead of the local-clock equivalents so date-boundary math stays
consistent with how the rest of the system treats time.
"""

from __future__ import annotations

from datetime import UTC, date, datetime


def utc_now() -> datetime:
    """Timezone-aware current instant in UTC."""
    return datetime.now(UTC)


def utc_today() -> date:
    """Current calendar date in UTC — use this instead of `date.today()`
    anywhere date boundaries are compared against UTC-anchored timestamps."""
    return datetime.now(UTC).date()

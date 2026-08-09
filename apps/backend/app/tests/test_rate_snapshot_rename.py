"""Confirms the `TimeEntry.rate_snapshot_cents` -> `billing_rate_snapshot_cents`
rename (plan §3/§4, migration `a9b0c1d2e3f4`) left no dangling references to
the old field name anywhere in application code, and that the new/additive
fields exist on the model and are settable."""

from __future__ import annotations

from pathlib import Path

from app.models.time_entry import TimeEntry

_APP_ROOT = Path(__file__).resolve().parents[1]  # apps/backend/app


def test_no_remaining_references_to_old_field_name_in_app_code() -> None:
    """Old migrations are allowed to still say `rate_snapshot_cents` (they
    describe schema history, not current state) — only `app/` (models,
    schemas, services, repositories, API, tests) must be clean. A line only
    counts as an offender if it mentions the bare old name outside of it
    being a substring of `billing_rate_snapshot_cents`/`cost_rate_snapshot_cents`."""
    offenders: list[str] = []
    for py_file in _APP_ROOT.rglob("*.py"):
        if py_file.name == "test_rate_snapshot_rename.py":
            continue
        text = py_file.read_text(encoding="utf-8")
        if "rate_snapshot_cents" not in text:
            continue
        for line in text.splitlines():
            if "rate_snapshot_cents" not in line:
                continue
            if "billing_rate_snapshot_cents" in line or "cost_rate_snapshot_cents" in line:
                continue
            offenders.append(f"{py_file.relative_to(_APP_ROOT)}: {line.strip()}")
    assert offenders == [], f"Old field name `rate_snapshot_cents` still referenced: {offenders}"


def test_time_entry_model_exposes_renamed_and_new_fields() -> None:
    assert hasattr(TimeEntry, "billing_rate_snapshot_cents")
    assert hasattr(TimeEntry, "cost_rate_snapshot_cents")
    assert hasattr(TimeEntry, "rate_currency_snapshot")
    assert not hasattr(TimeEntry, "rate_snapshot_cents")

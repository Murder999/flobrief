"""Runs the two new timestamp migrations (c9d0e1f2a3b4, d0e1f2a3b4c5) up and down
against real, disposable-database rows and asserts the *data*, not just that
Alembic exits 0:

  - c9d0e1f2a3b4 (deliverables.submitted_at/approved_at -> timezone-aware):
    a naive timestamp representing a known UTC instant must convert to the
    exact same instant as timestamptz, and downgrading must round-trip back
    to the same naive wall-clock value — no silent shift, no session-timezone
    dependence (the migration uses an explicit `AT TIME ZONE 'UTC'`, not an
    implicit cast).
  - d0e1f2a3b4c5 (deliverable_annotations/annotation_replies missing
    created_at/updated_at defaults): existing NULL rows must be backfilled to
    non-NULL, and the column must reject NULL afterwards.

All values are supplied explicitly (bypassing ORM-side Python defaults, which
raw SQL wouldn't apply anyway) so the test is not sensitive to unrelated
default-value changes elsewhere in the schema. Restores the schema to `head`
in a `finally` block so later tests in the suite are unaffected even if an
assertion fails.

`alembic.command.upgrade`/`downgrade` runs `alembic/env.py`, which calls
`logging.config.fileConfig(alembic.ini)`. That defaults to
`disable_existing_loggers=True`, which silently disables every already-created
logger not explicitly listed in `alembic.ini`'s `[loggers]` section (e.g.
`app.api.v1.deliverables`) for the rest of the *process* — breaking later
tests in the same pytest run that assert on log output (discovered while
writing test_annotation_notifications.py's failure-is-logged test, which
passed in isolation but failed after this file ran first). The autouse
fixture below re-enables every logger after each test here.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text

from alembic import command
from alembic.config import Config
from app.db.session import AsyncSessionLocal

BACKEND_DIR = Path(__file__).resolve().parents[2]

REV_BEFORE_TZ_FIX = "b8c9d0e1f2a3"
REV_TZ_FIX = "c9d0e1f2a3b4"
REV_ANNOTATION_DEFAULTS_FIX = "d0e1f2a3b4c5"


@pytest.fixture(autouse=True)
def _restore_loggers_disabled_by_alembic_fileconfig():
    yield
    for logger_obj in logging.Logger.manager.loggerDict.values():
        if isinstance(logger_obj, logging.Logger):
            logger_obj.disabled = False


def _alembic_config() -> Config:
    return Config(str(BACKEND_DIR / "alembic.ini"))


def _run(coro):
    """Run `coro` in its own event loop, then dispose the SQLAlchemy engine's
    connection pool before that loop closes.

    Each `_run()` call — and each `alembic.command.upgrade/downgrade` call,
    which internally does its own `asyncio.run(...)` per alembic/env.py —
    gets a fresh event loop. asyncpg connections are bound to the loop that
    opened them, so without disposing the pool inside the still-open loop,
    the next `_run()`/alembic call would try to reuse a connection tied to a
    now-closed loop and crash with `AttributeError: 'NoneType' object has no
    attribute 'send'` deep in asyncio's proactor transport.
    """

    async def _wrapped():
        try:
            return await coro
        finally:
            from app.db.session import engine

            await engine.dispose()

    return asyncio.run(_wrapped())


async def _seed_agency_user_brief(session, agency_id, user_id, brief_id) -> None:
    now = datetime.now(UTC)
    await session.execute(
        text(
            "INSERT INTO agencies (id, name, slug, status, created_at, updated_at) "
            "VALUES (:id, :name, :slug, 'active', :now, :now)"
        ),
        {
            "id": agency_id,
            "name": "Migration Test Agency",
            "slug": f"mig-test-{uuid.uuid4().hex[:10]}",
            "now": now,
        },
    )
    await session.execute(
        text(
            "INSERT INTO users (id, email, password_hash, full_name, user_type, "
            "is_active, is_verified, mfa_enabled, created_at, updated_at) "
            "VALUES (:id, :email, 'x', 'Migration Test User', 'agency_user', "
            "true, true, false, :now, :now)"
        ),
        {"id": user_id, "email": f"mig-test-{uuid.uuid4().hex[:10]}@test.local", "now": now},
    )
    await session.execute(
        text(
            "INSERT INTO briefs (id, agency_id, title, status, priority, created_by_id, "
            "created_at, updated_at) "
            "VALUES (:id, :agency_id, 'Migration Test Brief', 'draft', 'normal', "
            ":user_id, :now, :now)"
        ),
        {"id": brief_id, "agency_id": agency_id, "user_id": user_id, "now": now},
    )
    await session.commit()


async def _delete_seed(session, agency_id) -> None:
    # ON DELETE CASCADE from agencies covers briefs/deliverables/agency_members.
    await session.execute(text("DELETE FROM agencies WHERE id = :id"), {"id": agency_id})
    await session.commit()


class TestDeliverableTimezoneMigration:
    def test_upgrade_and_downgrade_preserve_the_same_instant(self) -> None:
        cfg = _alembic_config()
        agency_id = uuid.uuid4()
        user_id = uuid.uuid4()
        brief_id = uuid.uuid4()
        deliverable_id = uuid.uuid4()

        # A known instant, expressed as the naive wall-clock value the old
        # (bare DateTime = naive) column would have stored for it, per the
        # migration's own documented assumption: existing naive values are UTC.
        known_instant_utc = datetime(2026, 3, 10, 14, 30, 0, tzinfo=UTC)
        naive_value = known_instant_utc.replace(tzinfo=None)

        async def seed_and_insert_naive() -> None:
            async with AsyncSessionLocal() as session:
                await _seed_agency_user_brief(session, agency_id, user_id, brief_id)
                await session.execute(
                    text(
                        "INSERT INTO deliverables (id, agency_id, brief_id, title, "
                        "submitted_at, created_at, updated_at) "
                        "VALUES (:id, :agency_id, :brief_id, 'Migration Test Deliverable', "
                        ":submitted_at, now(), now())"
                    ),
                    {
                        "id": deliverable_id,
                        "agency_id": agency_id,
                        "brief_id": brief_id,
                        "submitted_at": naive_value,
                    },
                )
                await session.commit()

        async def read_submitted_at() -> datetime:
            async with AsyncSessionLocal() as session:
                row = (
                    await session.execute(
                        text("SELECT submitted_at FROM deliverables WHERE id = :id"),
                        {"id": deliverable_id},
                    )
                ).first()
                return row[0]

        async def cleanup() -> None:
            async with AsyncSessionLocal() as session:
                await _delete_seed(session, agency_id)

        command.downgrade(cfg, REV_BEFORE_TZ_FIX)
        try:
            _run(seed_and_insert_naive())

            command.upgrade(cfg, REV_TZ_FIX)
            stored_aware = _run(read_submitted_at())
            assert stored_aware.tzinfo is not None, "column must be timezone-aware after upgrade"
            assert stored_aware == known_instant_utc, (
                "upgrade must represent the exact same real-world instant, not a "
                "session-timezone-shifted one"
            )

            command.downgrade(cfg, REV_BEFORE_TZ_FIX)
            stored_naive = _run(read_submitted_at())
            assert stored_naive.tzinfo is None, "column must be naive again after downgrade"
            assert (
                stored_naive == naive_value
            ), "downgrade must round-trip to the original wall-clock value"
        finally:
            command.upgrade(cfg, "head")
            _run(cleanup())


class TestAnnotationTimestampDefaultsMigration:
    def test_backfills_existing_nulls_and_enforces_not_null_after_upgrade(self) -> None:
        cfg = _alembic_config()
        agency_id = uuid.uuid4()
        user_id = uuid.uuid4()
        brief_id = uuid.uuid4()
        deliverable_id = uuid.uuid4()
        annotation_id = uuid.uuid4()

        async def seed_null_annotation() -> None:
            async with AsyncSessionLocal() as session:
                await _seed_agency_user_brief(session, agency_id, user_id, brief_id)
                await session.execute(
                    text(
                        "INSERT INTO deliverables (id, agency_id, brief_id, title, "
                        "created_at, updated_at) "
                        "VALUES (:id, :agency_id, :brief_id, 'Migration Test Deliverable', "
                        "now(), now())"
                    ),
                    {"id": deliverable_id, "agency_id": agency_id, "brief_id": brief_id},
                )
                # created_at/updated_at deliberately omitted -> NULL, reproducing the
                # pre-fix bug (nullable, no server_default) this migration corrects.
                await session.execute(
                    text(
                        "INSERT INTO deliverable_annotations "
                        "(id, agency_id, brief_id, deliverable_id, version_number, label_number, "
                        "status, annotation_type, visibility, body) "
                        "VALUES (:id, :agency_id, :brief_id, :deliverable_id, 1, 1, "
                        "'open', 'general', 'client_visible', 'pre-migration NULL timestamp row')"
                    ),
                    {
                        "id": annotation_id,
                        "agency_id": agency_id,
                        "brief_id": brief_id,
                        "deliverable_id": deliverable_id,
                    },
                )
                await session.commit()

        async def read_timestamps() -> tuple:
            async with AsyncSessionLocal() as session:
                row = (
                    await session.execute(
                        text(
                            "SELECT created_at, updated_at FROM deliverable_annotations "
                            "WHERE id = :id"
                        ),
                        {"id": annotation_id},
                    )
                ).first()
                return row[0], row[1]

        async def column_rejects_null() -> bool:
            """True if the DB now rejects an explicit NULL created_at (NOT NULL enforced)."""
            async with AsyncSessionLocal() as session:
                try:
                    await session.execute(
                        text("UPDATE deliverable_annotations SET created_at = NULL WHERE id = :id"),
                        {"id": annotation_id},
                    )
                    await session.commit()
                    return False
                except Exception:
                    await session.rollback()
                    return True

        async def cleanup() -> None:
            async with AsyncSessionLocal() as session:
                await _delete_seed(session, agency_id)

        command.downgrade(cfg, REV_TZ_FIX)  # one revision before the annotation-defaults fix
        try:
            _run(seed_null_annotation())
            created_before, updated_before = _run(read_timestamps())
            assert (
                created_before is None and updated_before is None
            ), "test setup must reproduce the pre-fix NULL state before asserting the backfill"

            command.upgrade(cfg, REV_ANNOTATION_DEFAULTS_FIX)
            created_after, updated_after = _run(read_timestamps())
            assert created_after is not None, "created_at must be backfilled, not left NULL"
            assert updated_after is not None, "updated_at must be backfilled, not left NULL"
            assert _run(
                column_rejects_null()
            ), "created_at must be NOT NULL after upgrade — an explicit NULL write must fail"
        finally:
            command.upgrade(cfg, "head")
            _run(cleanup())

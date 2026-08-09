"""Computes which deliverables are the "latest" version within their own chain.

The ``deliverables`` table has no explicit version-chain link (no
``parent_id``/``supersedes_id``): a revision request mutates the *same* row
in place (status, revision_note, revision_count) rather than creating a new
historical row. So a brief's deliverables are, by default, all independent —
"Instagram post", "LinkedIn görsel" and "Video" submitted under one brief are
siblings, not versions of each other, and must all be independently latest.

The one case where multiple rows *do* represent the same logical deliverable
resubmitted over time is when an agency manually creates a new row reusing
the exact same title (e.g. after a rejection). That is the only reliable
signal already present in existing data — no schema change is needed to
express it. This module is the single shared computation both the agency
and brand portals read from, so neither reimplements the grouping logic.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deliverable import Deliverable


def compute_latest_version_ids(deliverables: Iterable[Deliverable]) -> set[uuid.UUID]:
    """Groups deliverables by normalized title; the newest row in each group
    (by submitted_at, falling back to created_at) is the latest version.
    A deliverable whose title is unique within the group is always latest."""
    groups: dict[str, list[Deliverable]] = {}
    for d in deliverables:
        key = d.title.strip().casefold()
        groups.setdefault(key, []).append(d)

    latest_ids: set[uuid.UUID] = set()
    for group in groups.values():
        newest = max(group, key=lambda d: d.submitted_at or d.created_at)
        latest_ids.add(newest.id)
    return latest_ids


async def get_latest_version_ids_for_brief(db: AsyncSession, brief_id: uuid.UUID) -> set[uuid.UUID]:
    """Fetches every non-deleted deliverable on the brief (any status, any
    portal's view) and returns the set of ids that are latest in their
    title chain. Callers must already have verified the caller's access to
    ``brief_id`` — this helper does no tenant scoping of its own."""
    rows = (
        (
            await db.execute(
                select(Deliverable).where(
                    Deliverable.brief_id == brief_id,
                    Deliverable.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    return compute_latest_version_ids(rows)

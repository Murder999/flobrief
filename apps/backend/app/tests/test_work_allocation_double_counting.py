"""THE critical correctness test for plan §5's planned-workload
double-counting rule, implemented as the pure function
`compute_brief_planned_minutes` in `capacity_calculation_service.py`.

Covers exactly the four required cases:
  (a) a brief whose tasks have `estimated_hours` set ignores
      `Brief.estimated_hours`/`estimated_hours_by_category` entirely.
  (b) a brief with no task estimates falls back to
      `estimated_hours_by_category` distributed by category-matching
      assignees, or to flat `estimated_hours` split evenly across
      `BriefAssignee` rows if no category breakdown.
  (c) a manual `WorkAllocation` for one specific (user, task) pair overrides
      only that assignee's auto-derived number without disturbing other
      assignees' numbers on the same brief.
  (d) a brief/task with zero estimate and no manual allocation contributes
      exactly 0 (not null), flagged via `has_estimate=False` for the
      "Süre tahmini yapılmamış" UI label.

Plus one end-to-end test that drives the same rule through real DB rows via
`CapacityCalculationService.user_capacity`, proving the pure function's
result is actually what the read-time aggregation wires up.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from app.db.session import AsyncSessionLocal
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.brief import Brief, BriefAssignee
from app.models.brief_task import BriefTask
from app.models.enums import AgencyMemberRole, AgencyMemberStatus, UserType
from app.models.user import User
from app.models.work_allocation import WorkAllocation
from app.services.capacity_calculation_service import (
    CapacityCalculationService,
    compute_brief_planned_minutes,
)


def _brief(**overrides) -> Brief:
    defaults = dict(
        id=uuid.uuid4(),
        agency_id=uuid.uuid4(),
        brand_id=None,
        title="Test Brief",
        status="draft",
        created_by_id=uuid.uuid4(),
        estimated_hours=None,
        estimated_hours_by_category=None,
    )
    defaults.update(overrides)
    return Brief(**defaults)


def _task(brief_id: uuid.UUID, **overrides) -> BriefTask:
    defaults = dict(
        id=uuid.uuid4(),
        agency_id=uuid.uuid4(),
        brief_id=brief_id,
        title="Test Task",
        assigned_to_id=None,
        estimated_hours=None,
    )
    defaults.update(overrides)
    return BriefTask(**defaults)


def _assignee(brief_id: uuid.UUID, user_id: uuid.UUID, **overrides) -> BriefAssignee:
    defaults = dict(id=uuid.uuid4(), brief_id=brief_id, user_id=user_id, participant_role=None)
    defaults.update(overrides)
    return BriefAssignee(**defaults)


def _manual_allocation(user_id: uuid.UUID, minutes: int, **overrides) -> WorkAllocation:
    defaults = dict(
        id=uuid.uuid4(),
        agency_id=uuid.uuid4(),
        user_id=user_id,
        start_date=date.today(),
        end_date=date.today(),
        allocated_minutes=minutes,
        allocation_source="manual",
        locked=False,
    )
    defaults.update(overrides)
    return WorkAllocation(**defaults)


# ------------------------------------------------------------------
# (a) tasks-present-means-tasks-win-wholesale


def test_a_task_estimates_ignore_brief_level_estimates_entirely() -> None:
    user1, user2 = uuid.uuid4(), uuid.uuid4()
    brief = _brief(estimated_hours=100.0, estimated_hours_by_category={"design": 50.0})
    tasks = [
        _task(brief.id, assigned_to_id=user1, estimated_hours=2.0),
        _task(brief.id, assigned_to_id=user2, estimated_hours=3.0),
    ]
    assignees = [_assignee(brief.id, user1), _assignee(brief.id, user2)]

    breakdown = compute_brief_planned_minutes(brief, tasks, assignees, [])

    assert breakdown.source == "tasks"
    assert breakdown.per_user_minutes[user1] == 120.0
    assert breakdown.per_user_minutes[user2] == 180.0
    assert breakdown.unassigned_minutes == 0.0
    # The brief's flat (100h) and category (50h design) numbers must never
    # leak in — total must be exactly the two tasks' minutes, nothing else.
    assert sum(breakdown.per_user_minutes.values()) == 300.0


def test_a_unassigned_task_with_estimate_goes_to_unassigned_bucket() -> None:
    user1 = uuid.uuid4()
    brief = _brief(estimated_hours=999.0)
    tasks = [
        _task(brief.id, assigned_to_id=user1, estimated_hours=1.0),
        _task(brief.id, assigned_to_id=None, estimated_hours=4.0),
    ]
    assignees = [_assignee(brief.id, user1)]

    breakdown = compute_brief_planned_minutes(brief, tasks, assignees, [])

    assert breakdown.per_user_minutes == {user1: 60.0}
    assert breakdown.unassigned_minutes == 240.0


# ------------------------------------------------------------------
# (b) category / flat fallback when no task has an estimate


def test_b_category_breakdown_distributed_to_matching_assignees_only() -> None:
    designer, smm, viewer = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    brief = _brief(
        estimated_hours=999.0,
        estimated_hours_by_category={"design": 4.0, "social_media": 2.0},
    )
    tasks: list[BriefTask] = []  # no tasks at all -> falls through to category
    assignees = [
        _assignee(brief.id, designer, participant_role="designer"),
        _assignee(brief.id, smm, participant_role="social_media_manager"),
        _assignee(brief.id, viewer, participant_role="viewer"),
    ]

    breakdown = compute_brief_planned_minutes(brief, tasks, assignees, [])

    assert breakdown.source == "category"
    assert breakdown.per_user_minutes[designer] == 240.0
    assert breakdown.per_user_minutes[smm] == 120.0
    assert viewer not in breakdown.per_user_minutes
    assert breakdown.unassigned_minutes == 0.0
    # The flat 999h number must never be used once a category breakdown exists.
    assert sum(breakdown.per_user_minutes.values()) == 360.0


def test_b_category_with_no_matching_assignees_is_unassigned() -> None:
    designer = uuid.uuid4()
    brief = _brief(estimated_hours_by_category={"copywriting": 3.0})
    assignees = [_assignee(brief.id, designer, participant_role="designer")]

    breakdown = compute_brief_planned_minutes(brief, [], assignees, [])

    assert designer not in breakdown.per_user_minutes
    assert breakdown.unassigned_minutes == 180.0


def test_b_flat_estimate_split_evenly_across_assignees_when_no_category() -> None:
    u1, u2, u3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    brief = _brief(estimated_hours=6.0, estimated_hours_by_category=None)
    assignees = [_assignee(brief.id, u1), _assignee(brief.id, u2), _assignee(brief.id, u3)]

    breakdown = compute_brief_planned_minutes(brief, [], assignees, [])

    assert breakdown.source == "flat"
    assert breakdown.per_user_minutes == {u1: 120.0, u2: 120.0, u3: 120.0}
    assert breakdown.unassigned_minutes == 0.0


def test_b_flat_estimate_with_no_assignees_is_unassigned() -> None:
    brief = _brief(estimated_hours=2.0)
    breakdown = compute_brief_planned_minutes(brief, [], [], [])
    assert breakdown.per_user_minutes == {}
    assert breakdown.unassigned_minutes == 120.0


# ------------------------------------------------------------------
# (c) manual/locked WorkAllocation overrides only its own assignee


def test_c_manual_allocation_overrides_only_that_assignee_not_others() -> None:
    user1, user2 = uuid.uuid4(), uuid.uuid4()
    brief = _brief()
    tasks = [
        _task(brief.id, assigned_to_id=user1, estimated_hours=2.0),
        _task(brief.id, assigned_to_id=user2, estimated_hours=3.0),
    ]
    assignees = [_assignee(brief.id, user1), _assignee(brief.id, user2)]
    manual = [_manual_allocation(user1, 999, locked=True)]

    breakdown = compute_brief_planned_minutes(brief, tasks, assignees, manual)

    assert breakdown.per_user_minutes[user1] == 999.0  # overridden, not added (120+999)
    assert breakdown.per_user_minutes[user2] == 180.0  # untouched


def test_c_manual_allocation_via_allocation_source_manual_also_overrides() -> None:
    """`locked` and `allocation_source == "manual"` are independently
    sufficient — a locked-False, source="manual" row must still win."""
    user1 = uuid.uuid4()
    brief = _brief()
    tasks = [_task(brief.id, assigned_to_id=user1, estimated_hours=2.0)]
    assignees = [_assignee(brief.id, user1)]
    manual = [_manual_allocation(user1, 45, locked=False, allocation_source="manual")]

    breakdown = compute_brief_planned_minutes(brief, tasks, assignees, manual)

    assert breakdown.per_user_minutes[user1] == 45.0


def test_c_auto_derived_allocation_source_does_not_override() -> None:
    """A row that is neither locked nor manual-sourced (e.g. a prior
    auto_task sweep) must NOT trigger the override — only manual/locked wins."""
    user1 = uuid.uuid4()
    brief = _brief()
    tasks = [_task(brief.id, assigned_to_id=user1, estimated_hours=2.0)]
    assignees = [_assignee(brief.id, user1)]
    non_manual = [_manual_allocation(user1, 999, locked=False, allocation_source="auto_task")]

    breakdown = compute_brief_planned_minutes(brief, tasks, assignees, non_manual)

    assert breakdown.per_user_minutes[user1] == 120.0  # auto-derived value stands


# ------------------------------------------------------------------
# (d) zero estimate, no manual allocation -> exactly 0, not null, flagged


def test_d_no_estimate_and_no_manual_allocation_contributes_exactly_zero() -> None:
    user1 = uuid.uuid4()
    brief = _brief(estimated_hours=None, estimated_hours_by_category=None)
    tasks = [_task(brief.id, assigned_to_id=user1, estimated_hours=None)]
    assignees = [_assignee(brief.id, user1)]

    breakdown = compute_brief_planned_minutes(brief, tasks, assignees, [])

    assert breakdown.source == "none"
    assert breakdown.has_estimate is False
    assert breakdown.per_user_minutes == {}
    assert breakdown.per_user_minutes.get(user1, 0.0) == 0.0  # exactly 0, never null
    assert breakdown.unassigned_minutes == 0.0


def test_d_manual_allocation_alone_still_counts_and_flags_has_estimate() -> None:
    """Even with zero auto-derivable estimate, a manual allocation is real
    planned work — `has_estimate` flips to True and the user's number is the
    manual figure, not 0."""
    user1 = uuid.uuid4()
    brief = _brief(estimated_hours=None, estimated_hours_by_category=None)
    tasks = [_task(brief.id, assigned_to_id=user1, estimated_hours=None)]
    assignees = [_assignee(brief.id, user1)]
    manual = [_manual_allocation(user1, 60, locked=True)]

    breakdown = compute_brief_planned_minutes(brief, tasks, assignees, manual)

    assert breakdown.has_estimate is True
    assert breakdown.per_user_minutes[user1] == 60.0


# ------------------------------------------------------------------
# End-to-end: the same rule wired through real DB rows and the aggregation
# service (not just the pure function).


async def test_double_counting_rule_wired_end_to_end_through_db() -> None:
    async with AsyncSessionLocal() as session:
        suffix = uuid.uuid4().hex[:10]
        agency = Agency(id=uuid.uuid4(), name="DblCount Agency", slug=f"dblcount-{suffix}")
        session.add(agency)
        await session.flush()

        creator = User(
            id=uuid.uuid4(),
            email=f"dblcount-creator-{suffix}@test.local",
            password_hash="not-a-real-hash-test-fixture-only",
            full_name="Creator",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        designer = User(
            id=uuid.uuid4(),
            email=f"dblcount-designer-{suffix}@test.local",
            password_hash="not-a-real-hash-test-fixture-only",
            full_name="Designer",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        session.add_all([creator, designer])
        await session.flush()

        session.add_all(
            [
                AgencyMember(
                    id=uuid.uuid4(),
                    agency_id=agency.id,
                    user_id=creator.id,
                    role=AgencyMemberRole.ADMIN.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
                AgencyMember(
                    id=uuid.uuid4(),
                    agency_id=agency.id,
                    user_id=designer.id,
                    role=AgencyMemberRole.DESIGNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
            ]
        )

        brief = Brief(
            id=uuid.uuid4(),
            agency_id=agency.id,
            title="DB Brief",
            status="draft",
            created_by_id=creator.id,
            estimated_hours=500.0,  # must be ignored: tasks win
        )
        session.add(brief)
        await session.flush()

        task = BriefTask(
            id=uuid.uuid4(),
            agency_id=agency.id,
            brief_id=brief.id,
            title="DB Task",
            assigned_to_id=designer.id,
            estimated_hours=2.0,
        )
        session.add(task)

        # A manual, locked allocation for the same (designer, task) pair —
        # must override the 2h(=120min) auto-derived figure entirely.
        manual_alloc = WorkAllocation(
            id=uuid.uuid4(),
            agency_id=agency.id,
            brief_id=brief.id,
            task_id=task.id,
            user_id=designer.id,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=1),
            allocated_minutes=500,
            allocation_source="manual",
            locked=True,
        )
        session.add(manual_alloc)
        await session.commit()

    async with AsyncSessionLocal() as session:
        report = await CapacityCalculationService(session).user_capacity(
            agency.id, designer.id, date.today(), date.today() + timedelta(days=1)
        )

    # 500 planned minutes from the manual override, never the 120min
    # auto-derived task figure, and never anything derived from the
    # brief's 500-hour flat estimate.
    assert report.planned_minutes == 500.0

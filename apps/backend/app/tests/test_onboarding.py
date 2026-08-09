"""Real-Postgres tests for the interactive onboarding system (OnboardingProgress
/ OnboardingStepState models + OnboardingService + /onboarding/progress +
/brand-portal/onboarding/progress). Uses the shared `tenants` fixture."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.agency_member import AgencyMember
from app.models.enums import AgencyMemberRole, AgencyMemberStatus
from app.tests.conftest import Tenant, _make_user, agency_headers, brand_headers

pytestmark = pytest.mark.asyncio


async def _add_agency_member(tenant: Tenant, role: str) -> tuple[uuid.UUID, str]:
    async with AsyncSessionLocal() as session:
        user = await _make_user(session, f"member-{uuid.uuid4().hex[:8]}@test.local", "agency_user")
        await session.flush()
        session.add(
            AgencyMember(
                id=uuid.uuid4(),
                agency_id=tenant.agency_id,
                user_id=user.id,
                role=role,
                status=AgencyMemberStatus.ACTIVE.value,
            )
        )
        await session.commit()
        return user.id, create_access_token(str(user.id))


# ── Agency owner onboarding: real data drives completion ────────────────────


async def test_progress_persists_across_requests(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    tenant_a, _ = tenants
    headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)

    first = await client.get("/api/v1/onboarding/progress", headers=headers)
    second = await client.get("/api/v1/onboarding/progress", headers=headers)
    assert first.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["onboarding_type"] == "agency_owner_admin"
    assert first.json()["version"] == 1


async def test_first_brand_and_first_brief_steps_reflect_real_fixture_data(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    tenant_a, _ = tenants
    resp = await client.get(
        "/api/v1/onboarding/progress",
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    steps = {s["key"]: s for s in resp.json()["steps"]}
    # The `tenants` fixture already creates a real brand + brief + deliverable
    # for tenant_a, so all three reflect that real data immediately.
    assert steps["first_brand"]["completed"] is True
    assert steps["first_brief"]["completed"] is True
    assert steps["first_deliverable"]["completed"] is True
    # No WorkSchedule row exists yet — capacity was never actually configured.
    assert steps["capacity"]["completed"] is False
    # Only the fixture's single admin exists — no one has been invited yet.
    assert steps["invite_team"]["completed"] is False


async def test_invite_team_step_flips_true_after_real_invite(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    tenant_a, _ = tenants
    headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
    before = await client.get("/api/v1/onboarding/progress", headers=headers)
    assert {s["key"]: s["completed"] for s in before.json()["steps"]}["invite_team"] is False

    await _add_agency_member(tenant_a, AgencyMemberRole.DESIGNER.value)

    after = await client.get("/api/v1/onboarding/progress", headers=headers)
    assert {s["key"]: s["completed"] for s in after.json()["steps"]}["invite_team"] is True


async def test_mention_step_flips_true_only_after_real_mention(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    tenant_a, _ = tenants
    headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
    before = await client.get("/api/v1/onboarding/progress", headers=headers)
    step_before = {s["key"]: s["completed"] for s in before.json()["steps"]}
    assert step_before["comment_mention_annotation"] is False

    member_id, _ = await _add_agency_member(tenant_a, AgencyMemberRole.DESIGNER.value)
    async with AsyncSessionLocal() as session:
        from app.models.user import User

        member = await session.get(User, member_id)
        member_name = member.full_name

    await client.post(
        f"/api/v1/briefs/{tenant_a.brief_id}/threads",
        json={
            "thread_type": "brief",
            "initial_comment": f"@{member_name} bakar mısın?",
            "visibility": "internal",
            "mentioned_user_ids": [str(member_id)],
        },
        headers=headers,
    )

    after = await client.get("/api/v1/onboarding/progress", headers=headers)
    step_after = {s["key"]: s["completed"] for s in after.json()["steps"]}
    assert step_after["comment_mention_annotation"] is True


async def test_view_step_requires_real_seen_call_not_just_a_click(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    tenant_a, _ = tenants
    headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)

    before = await client.get("/api/v1/onboarding/progress", headers=headers)
    assert {s["key"]: s["completed"] for s in before.json()["steps"]}["welcome"] is False

    seen_resp = await client.post("/api/v1/onboarding/progress/step/welcome/seen", headers=headers)
    assert seen_resp.status_code == 200
    steps = {s["key"]: s["completed"] for s in seen_resp.json()["steps"]}
    assert steps["welcome"] is True


async def test_unknown_step_key_404s(client: AsyncClient, tenants: tuple[Tenant, Tenant]) -> None:
    tenant_a, _ = tenants
    resp = await client.post(
        "/api/v1/onboarding/progress/step/not_a_real_step/seen",
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 404


async def test_skip_step_counts_toward_progress_without_faking_completion(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    tenant_a, _ = tenants
    headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
    resp = await client.post("/api/v1/onboarding/progress/step/capacity/skip", headers=headers)
    assert resp.status_code == 200
    step = next(s for s in resp.json()["steps"] if s["key"] == "capacity")
    assert step["skipped"] is True
    assert step["completed"] is False  # skipped is not the same as genuinely completed


async def test_dismiss_and_resume(client: AsyncClient, tenants: tuple[Tenant, Tenant]) -> None:
    tenant_a, _ = tenants
    headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)

    dismissed = await client.post("/api/v1/onboarding/progress/dismiss", headers=headers)
    assert dismissed.json()["dismissed_at"] is not None

    resumed = await client.post("/api/v1/onboarding/progress/resume", headers=headers)
    assert resumed.json()["dismissed_at"] is None


# ── Role-based step sets ─────────────────────────────────────────────────────


async def test_agency_member_gets_different_step_set_than_owner(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    tenant_a, _ = tenants
    member_id, member_token = await _add_agency_member(tenant_a, AgencyMemberRole.DESIGNER.value)

    owner_resp = await client.get(
        "/api/v1/onboarding/progress",
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    member_resp = await client.get(
        "/api/v1/onboarding/progress",
        headers=agency_headers(member_token, tenant_a.agency_id),
    )
    assert owner_resp.json()["onboarding_type"] == "agency_owner_admin"
    assert member_resp.json()["onboarding_type"] == "agency_member"
    owner_keys = {s["key"] for s in owner_resp.json()["steps"]}
    member_keys = {s["key"] for s in member_resp.json()["steps"]}
    assert owner_keys != member_keys
    assert "invite_team" in owner_keys
    assert "invite_team" not in member_keys


async def test_agency_member_progress_is_scoped_to_that_member_not_owner(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    """IDOR-adjacent: a member's own onboarding progress row must be theirs,
    never silently shared with/overwritten by the owner's."""
    tenant_a, _ = tenants
    _, member_token = await _add_agency_member(tenant_a, AgencyMemberRole.DESIGNER.value)

    owner_resp = await client.get(
        "/api/v1/onboarding/progress",
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    member_resp = await client.get(
        "/api/v1/onboarding/progress",
        headers=agency_headers(member_token, tenant_a.agency_id),
    )
    assert owner_resp.json()["id"] != member_resp.json()["id"]

    await client.post(
        "/api/v1/onboarding/progress/dismiss",
        headers=agency_headers(member_token, tenant_a.agency_id),
    )
    owner_after = await client.get(
        "/api/v1/onboarding/progress",
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert owner_after.json()["dismissed_at"] is None  # member's dismiss didn't affect owner


# ── Brand onboarding ─────────────────────────────────────────────────────────


async def test_brand_user_gets_brand_onboarding_type(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    tenant_a, _ = tenants
    resp = await client.get(
        "/api/v1/brand-portal/onboarding/progress",
        headers=brand_headers(tenant_a.brand_manager_token),
    )
    assert resp.status_code == 200
    assert resp.json()["onboarding_type"] == "brand_user"
    keys = {s["key"] for s in resp.json()["steps"]}
    assert keys == {
        "portal_intro",
        "view_briefs",
        "deliverable_preview",
        "annotation",
        "comment_mention",
        "request_revision",
        "approve",
        "calendar_invoices",
    }


async def test_brand_annotation_step_flips_true_after_real_annotation(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    tenant_a, _ = tenants
    # brand_viewer (not brand_manager — the `tenants` fixture already seeded
    # one annotation authored by brand_manager, so their step starts True)
    # has authored nothing yet, giving a clean False→True transition.
    headers = brand_headers(tenant_a.brand_viewer_token)

    before = await client.get("/api/v1/brand-portal/onboarding/progress", headers=headers)
    assert {s["key"]: s["completed"] for s in before.json()["steps"]}["annotation"] is False

    ann_resp = await client.post(
        f"/api/v1/brand-portal/deliverables/{tenant_a.deliverable_id}/annotations",
        json={"version_number": 1, "annotation_type": "general", "body": "Burayı düzeltelim."},
        headers=headers,
    )
    assert ann_resp.status_code == 201

    after = await client.get("/api/v1/brand-portal/onboarding/progress", headers=headers)
    assert {s["key"]: s["completed"] for s in after.json()["steps"]}["annotation"] is True


async def test_agency_and_brand_onboarding_do_not_cross_contaminate(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    tenant_a, _ = tenants
    agency_resp = await client.get(
        "/api/v1/onboarding/progress",
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    brand_resp = await client.get(
        "/api/v1/brand-portal/onboarding/progress",
        headers=brand_headers(tenant_a.brand_manager_token),
    )
    assert agency_resp.json()["id"] != brand_resp.json()["id"]
    assert agency_resp.json()["onboarding_type"] != brand_resp.json()["onboarding_type"]


async def test_cross_tenant_owners_get_fully_independent_progress_rows(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    """Both tenants' owners resolve to the same `onboarding_type`
    (agency_owner_admin) — the uniqueness constraint is (user_id,
    onboarding_type), not (agency_id, onboarding_type), so this proves two
    different users sharing the same onboarding_type never collide on the
    same row, and that dismissing tenant A's tour never touches tenant B's."""
    tenant_a, tenant_b = tenants

    resp_a = await client.get(
        "/api/v1/onboarding/progress",
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    resp_b = await client.get(
        "/api/v1/onboarding/progress",
        headers=agency_headers(tenant_b.agency_token, tenant_b.agency_id),
    )
    assert resp_a.status_code == 200 and resp_b.status_code == 200
    onboarding_type_a = resp_a.json()["onboarding_type"]
    onboarding_type_b = resp_b.json()["onboarding_type"]
    assert onboarding_type_a == onboarding_type_b == "agency_owner_admin"
    assert resp_a.json()["id"] != resp_b.json()["id"]

    dismiss_a = await client.post(
        "/api/v1/onboarding/progress/dismiss",
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert dismiss_a.json()["dismissed_at"] is not None

    still_active_b = await client.get(
        "/api/v1/onboarding/progress",
        headers=agency_headers(tenant_b.agency_token, tenant_b.agency_id),
    )
    assert still_active_b.json()["dismissed_at"] is None


# ── Security / edge-case coverage ────────────────────────────────────────────


async def test_client_cannot_override_onboarding_type_via_extra_body_fields(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    """No endpoint declares a request body accepting `onboarding_type` (or
    any other identity field) — extra JSON fields are simply ignored by
    FastAPI's routing since no schema binds to them. This proves the
    server-derived value wins regardless of what a client sends."""
    tenant_a, _ = tenants
    resp = await client.post(
        "/api/v1/onboarding/progress/dismiss",
        json={
            "onboarding_type": "brand_user",
            "user_id": str(uuid.uuid4()),
            "agency_id": str(uuid.uuid4()),
        },
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 200
    # real role wins, not the injected value
    assert resp.json()["onboarding_type"] == "agency_owner_admin"


async def test_step_key_valid_for_other_role_404s_for_this_role(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    """`invite_team` is a real step key — just not for this role's step set —
    so it must 404 exactly like a nonexistent key, not silently succeed."""
    tenant_a, _ = tenants
    _, member_token = await _add_agency_member(tenant_a, AgencyMemberRole.DESIGNER.value)
    resp = await client.post(
        "/api/v1/onboarding/progress/step/invite_team/seen",
        headers=agency_headers(member_token, tenant_a.agency_id),
    )
    assert resp.status_code == 404


async def test_marking_action_step_seen_does_not_fake_completion(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    """`capacity` is an action-kind step (real completion needs a
    WorkSchedule row, not seeded by the `tenants` fixture); calling
    `.../seen` on it — e.g. a stray or spoofed call — must not flip its
    `completed` flag."""
    tenant_a, _ = tenants
    headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)

    before = await client.get("/api/v1/onboarding/progress", headers=headers)
    assert {s["key"]: s["completed"] for s in before.json()["steps"]}["capacity"] is False

    seen_resp = await client.post("/api/v1/onboarding/progress/step/capacity/seen", headers=headers)
    assert seen_resp.status_code == 200
    assert {s["key"]: s["completed"] for s in seen_resp.json()["steps"]}["capacity"] is False


async def test_completed_onboarding_does_not_reset_or_reopen_on_later_read(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    """Once every step is completed/skipped, `completed_at` is set once and
    stays set — re-reading progress must not clear it or force the tour
    back open."""
    tenant_a, _ = tenants
    headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)

    first = await client.get("/api/v1/onboarding/progress", headers=headers)
    for step in first.json()["steps"]:
        await client.post(f"/api/v1/onboarding/progress/step/{step['key']}/skip", headers=headers)

    after_skip = await client.get("/api/v1/onboarding/progress", headers=headers)
    assert after_skip.json()["completed_at"] is not None
    completed_at = after_skip.json()["completed_at"]

    again = await client.get("/api/v1/onboarding/progress", headers=headers)
    assert again.json()["completed_at"] == completed_at  # stable, not reset


async def test_version_defaults_to_current_and_is_stable_across_requests(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    """`version` is write-once at creation (CURRENT_ONBOARDING_VERSION) and is
    never read/compared anywhere else in the service today — this test
    documents that real behavior (no migration/reset logic exists yet)
    rather than asserting an upgrade flow that isn't implemented."""
    tenant_a, _ = tenants
    headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
    first = await client.get("/api/v1/onboarding/progress", headers=headers)
    second = await client.get("/api/v1/onboarding/progress", headers=headers)
    assert first.json()["version"] == 1
    assert second.json()["version"] == 1


async def test_deactivated_user_cannot_access_onboarding_progress(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    """Reuses the shared `is_active` gate enforced for every authenticated
    endpoint (app/core/auth_dependencies.py:get_current_user) — no
    onboarding-specific plumbing needed; a deactivated user is already
    rejected before reaching the onboarding router."""
    tenant_a, _ = tenants
    member_id, member_token = await _add_agency_member(tenant_a, AgencyMemberRole.DESIGNER.value)

    from app.models.user import User

    async with AsyncSessionLocal() as session:
        user = await session.get(User, member_id)
        user.is_active = False
        await session.commit()

    resp = await client.get(
        "/api/v1/onboarding/progress",
        headers=agency_headers(member_token, tenant_a.agency_id),
    )
    assert resp.status_code == 401


async def test_rapid_duplicate_seen_calls_stay_idempotent(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    """Two back-to-back `.../seen` calls for the same view step must not
    create duplicate step-state rows or double-count anything — the unique
    constraint on (onboarding_progress_id, step_key) backs this."""
    tenant_a, _ = tenants
    headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)

    first = await client.post(
        "/api/v1/onboarding/progress/step/preview_center/seen", headers=headers
    )
    second = await client.post(
        "/api/v1/onboarding/progress/step/preview_center/seen", headers=headers
    )
    assert first.status_code == 200
    assert second.status_code == 200
    step = {s["key"]: s for s in second.json()["steps"]}["preview_center"]
    assert step["completed"] is True

    from app.models.onboarding import OnboardingProgress, OnboardingStepState

    async with AsyncSessionLocal() as session:
        progress = (
            await session.execute(
                OnboardingProgress.__table__.select().where(
                    OnboardingProgress.user_id == tenant_a.agency_user_id
                )
            )
        ).fetchone()
        rows = (
            await session.execute(
                OnboardingStepState.__table__.select().where(
                    OnboardingStepState.onboarding_progress_id == progress.id,
                    OnboardingStepState.step_key == "preview_center",
                )
            )
        ).fetchall()
        assert len(rows) == 1


async def test_onboarding_metadata_never_exposed_or_settable(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    """`onboarding_metadata` (JSONB bookkeeping column) has no request schema
    exposing it and is absent from every response — confirms there is no
    mass-assignment surface to test against, rather than inventing one."""
    tenant_a, _ = tenants
    resp = await client.get(
        "/api/v1/onboarding/progress",
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert "onboarding_metadata" not in resp.json()

    posted = await client.post(
        "/api/v1/onboarding/progress/dismiss",
        json={"onboarding_metadata": {"is_admin": True}},
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert "onboarding_metadata" not in posted.json()

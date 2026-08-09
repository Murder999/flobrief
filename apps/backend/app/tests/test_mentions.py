"""Real-Postgres tests for the @mention system (Mention model + MentionService
+ /mentions/candidates + /brand-portal/mentions/candidates + mention wiring
in comment/annotation endpoints). Uses the shared `tenants` fixture from
conftest.py (two fully independent tenants) for tenant-isolation coverage.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.agency_member import AgencyMember
from app.models.brief import BriefAssignee
from app.models.enums import AgencyMemberRole, AgencyMemberStatus
from app.models.mention import Mention
from app.models.notification import Notification
from app.models.user import User
from app.tests.conftest import Tenant, _make_user, agency_headers, brand_headers

pytestmark = pytest.mark.asyncio


async def _add_agency_member(
    tenant: Tenant, full_name: str, role: str, email_suffix: str
) -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        user = await _make_user(session, f"{email_suffix}@test.local", "agency_user")
        user.full_name = full_name
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
        return user.id


async def _assign_to_brief(tenant: Tenant, user_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        session.add(BriefAssignee(id=uuid.uuid4(), brief_id=tenant.brief_id, user_id=user_id))
        await session.commit()


# ── Candidate filtering ──────────────────────────────────────────────────────


async def test_agency_candidates_excludes_viewer_and_requester(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    tenant_a, _ = tenants
    designer_id = await _add_agency_member(
        tenant_a,
        "Deniz Tasarımcı",
        AgencyMemberRole.DESIGNER.value,
        f"designer-{uuid.uuid4().hex[:8]}",
    )
    viewer_id = await _add_agency_member(
        tenant_a, "Vahit İzleyici", AgencyMemberRole.VIEWER.value, f"viewer-{uuid.uuid4().hex[:8]}"
    )

    resp = await client.get(
        "/api/v1/mentions/candidates",
        params={"source_type": "comment"},
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 200
    ids = {item["user_id"] for item in resp.json()["items"]}
    assert str(designer_id) in ids
    assert str(viewer_id) not in ids  # viewer role excluded (§C)
    assert str(tenant_a.agency_user_id) not in ids  # requester excluded


async def test_agency_candidates_tenant_isolated(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    tenant_a, tenant_b = tenants
    resp = await client.get(
        "/api/v1/mentions/candidates",
        params={"source_type": "comment"},
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    ids = {item["user_id"] for item in resp.json()["items"]}
    assert str(tenant_b.agency_user_id) not in ids


async def test_brand_candidates_exclude_unassigned_agency_directory(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    tenant_a, _ = tenants
    unrelated_id = await _add_agency_member(
        tenant_a,
        "İlgisiz Geliştirici",
        AgencyMemberRole.DEVELOPER.value,
        f"unrelated-{uuid.uuid4().hex[:8]}",
    )
    assigned_id = await _add_agency_member(
        tenant_a,
        "Atanmış Geliştirici",
        AgencyMemberRole.DEVELOPER.value,
        f"assigned-{uuid.uuid4().hex[:8]}",
    )
    await _assign_to_brief(tenant_a, assigned_id)

    resp = await client.get(
        "/api/v1/brand-portal/mentions/candidates",
        params={"source_type": "annotation", "source_id": str(tenant_a.annotation_id)},
        headers=brand_headers(tenant_a.brand_manager_token),
    )
    assert resp.status_code == 200
    ids = {item["user_id"] for item in resp.json()["items"]}
    assert str(assigned_id) in ids  # assigned to the brief → visible
    assert str(unrelated_id) not in ids  # not assigned → hidden from brand directory
    assert str(tenant_a.agency_user_id) in ids  # owner/admin always reachable


async def test_candidate_query_matches_turkish_name_regardless_of_case_or_diacritics(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    """`_normalize()` NFKD-strips diacritics and casefolds before matching, so
    a query for "sen" (no diacritics, lowercase) must still find "Şenay
    Yılmazoğlu" — and an unrelated query must return nothing. Also covers the
    Turkish dotted/dotless I pair (İ/I/i/ı), which `str.lower()` alone gets
    wrong but casefold()+NFKD handles correctly."""
    tenant_a, _ = tenants
    target_id = await _add_agency_member(
        tenant_a,
        "Şenay Yılmazoğlu",
        AgencyMemberRole.DESIGNER.value,
        f"turkish-{uuid.uuid4().hex[:8]}",
    )

    for query in ("sen", "SEN", "yilmaz", "Yılmaz", "İ"):
        resp = await client.get(
            "/api/v1/mentions/candidates",
            params={"source_type": "comment", "query": query},
            headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
        )
        assert resp.status_code == 200
        ids = {item["user_id"] for item in resp.json()["items"]}
        assert str(target_id) in ids, f"query {query!r} should match Şenay Yılmazoğlu"

    resp = await client.get(
        "/api/v1/mentions/candidates",
        params={"source_type": "comment", "query": "zzz-no-such-person"},
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 200
    assert resp.json()["items"] == []


# ── Create / dedupe / self-mention / tenant validation ──────────────────────


async def test_comment_mention_creates_notification(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    tenant_a, _ = tenants
    mentioned_id = await _add_agency_member(
        tenant_a,
        "Merve Yönetici",
        AgencyMemberRole.BRAND_MANAGER.value,
        f"merve-{uuid.uuid4().hex[:8]}",
    )

    resp = await client.post(
        f"/api/v1/briefs/{tenant_a.brief_id}/threads",
        json={
            "thread_type": "brief",
            "initial_comment": "Merhaba @Merve, bir bakabilir misin?",
            "visibility": "internal",
            "mentioned_user_ids": [str(mentioned_id)],
        },
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 201
    body = resp.json()
    comment = body["comments"][0]
    assert [m["mentioned_user_id"] for m in comment["mentions"]] == [str(mentioned_id)]

    async with AsyncSessionLocal() as session:
        notif = await session.scalar(
            select(Notification).where(Notification.user_id == mentioned_id)
        )
        assert notif is not None
        assert notif.event_type == "mention.in_comment"


async def test_mention_dropped_if_name_not_in_body(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    tenant_a, _ = tenants
    mentioned_id = await _add_agency_member(
        tenant_a,
        "Selin Tasarımcı",
        AgencyMemberRole.DESIGNER.value,
        f"selin-{uuid.uuid4().hex[:8]}",
    )

    resp = await client.post(
        f"/api/v1/briefs/{tenant_a.brief_id}/threads",
        json={
            "thread_type": "brief",
            "initial_comment": "Bu yorumda kimseden bahsetmiyorum.",
            "visibility": "internal",
            "mentioned_user_ids": [str(mentioned_id)],
        },
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 201
    assert resp.json()["comments"][0]["mentions"] == []


async def test_self_mention_produces_no_notification(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    tenant_a, _ = tenants
    async with AsyncSessionLocal() as session:
        me = await session.get(User, tenant_a.agency_user_id)
        my_name = me.full_name

    resp = await client.post(
        f"/api/v1/briefs/{tenant_a.brief_id}/threads",
        json={
            "thread_type": "brief",
            "initial_comment": f"Ben @{my_name} kendimi etiketliyorum.",
            "visibility": "internal",
            "mentioned_user_ids": [str(tenant_a.agency_user_id)],
        },
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 201
    assert resp.json()["comments"][0]["mentions"] == []


async def test_duplicate_mention_id_produces_single_mention_row(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    tenant_a, _ = tenants
    mentioned_id = await _add_agency_member(
        tenant_a,
        "Ceren Yönetici",
        AgencyMemberRole.BRAND_MANAGER.value,
        f"ceren-{uuid.uuid4().hex[:8]}",
    )

    resp = await client.post(
        f"/api/v1/briefs/{tenant_a.brief_id}/threads",
        json={
            "thread_type": "brief",
            "initial_comment": "@Ceren @Ceren lütfen bak.",
            "visibility": "internal",
            "mentioned_user_ids": [str(mentioned_id), str(mentioned_id)],
        },
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 201
    comment_id = uuid.UUID(resp.json()["comments"][0]["id"])

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(Mention.__table__.select().where(Mention.source_id == comment_id))
        ).fetchall()
        assert len(rows) == 1


async def test_cross_tenant_mention_id_is_silently_rejected(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    tenant_a, tenant_b = tenants
    async with AsyncSessionLocal() as session:
        other_user = await session.get(User, tenant_b.agency_user_id)
        other_name = other_user.full_name

    resp = await client.post(
        f"/api/v1/briefs/{tenant_a.brief_id}/threads",
        json={
            "thread_type": "brief",
            "initial_comment": f"@{other_name} buraya bak (başka ajans üyesi).",
            "visibility": "internal",
            "mentioned_user_ids": [str(tenant_b.agency_user_id)],
        },
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 201
    assert resp.json()["comments"][0]["mentions"] == []

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                Mention.__table__.select().where(
                    Mention.mentioned_user_id == tenant_b.agency_user_id
                )
            )
        ).fetchall()
        assert len(rows) == 0


async def test_edit_comment_notifies_only_newly_added_mention(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    tenant_a, _ = tenants
    first_id = await _add_agency_member(
        tenant_a, "Ada Birinci", AgencyMemberRole.DESIGNER.value, f"ada-{uuid.uuid4().hex[:8]}"
    )
    second_id = await _add_agency_member(
        tenant_a, "Beste İkinci", AgencyMemberRole.DESIGNER.value, f"beste-{uuid.uuid4().hex[:8]}"
    )

    create_resp = await client.post(
        f"/api/v1/briefs/{tenant_a.brief_id}/threads",
        json={
            "thread_type": "brief",
            "initial_comment": "@Ada bakar mısın?",
            "visibility": "internal",
            "mentioned_user_ids": [str(first_id)],
        },
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    thread_id = create_resp.json()["id"]
    comment_id = create_resp.json()["comments"][0]["id"]

    edit_resp = await client.patch(
        f"/api/v1/threads/{thread_id}/comments/{comment_id}",
        json={
            "body": "@Ada ve @Beste bakar mısınız?",
            "mentioned_user_ids": [str(first_id), str(second_id)],
        },
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert edit_resp.status_code == 200
    mention_ids = {m["mentioned_user_id"] for m in edit_resp.json()["mentions"]}
    assert mention_ids == {str(first_id), str(second_id)}

    async with AsyncSessionLocal() as session:
        first_notifs = (
            await session.execute(
                Notification.__table__.select().where(Notification.user_id == first_id)
            )
        ).fetchall()
        second_notifs = (
            await session.execute(
                Notification.__table__.select().where(Notification.user_id == second_id)
            )
        ).fetchall()
        # First mention notified once (create), not again on edit; second notified once (edit).
        assert len(first_notifs) == 1
        assert len(second_notifs) == 1


# ── Annotation mention binding ───────────────────────────────────────────────


async def test_annotation_mention_binding(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    tenant_a, _ = tenants
    mentioned_id = await _add_agency_member(
        tenant_a,
        "Onur Geliştirici",
        AgencyMemberRole.DEVELOPER.value,
        f"onur-{uuid.uuid4().hex[:8]}",
    )

    resp = await client.post(
        f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{tenant_a.deliverable_id}/annotations",
        json={
            "version_number": 1,
            "annotation_type": "general",
            "visibility": "internal",
            "body": "@Onur bu alanı kontrol eder misin?",
            "mentioned_user_ids": [str(mentioned_id)],
        },
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 201
    mentions = resp.json()["mentions"]
    assert [m["mentioned_user_id"] for m in mentions] == [str(mentioned_id)]

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                Mention.__table__.select().where(Mention.source_type == "annotation")
            )
        ).fetchall()
        assert any(str(r.mentioned_user_id) == str(mentioned_id) for r in rows)


# ── Deleted-user fallback ────────────────────────────────────────────────────


async def test_deleted_mentioned_user_shows_inactive_fallback(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    tenant_a, _ = tenants
    mentioned_id = await _add_agency_member(
        tenant_a, "Eski Üye", AgencyMemberRole.DESIGNER.value, f"eski-{uuid.uuid4().hex[:8]}"
    )

    create_resp = await client.post(
        f"/api/v1/briefs/{tenant_a.brief_id}/threads",
        json={
            "thread_type": "brief",
            "initial_comment": "@Eski Üye bakar mısın?",
            "visibility": "internal",
            "mentioned_user_ids": [str(mentioned_id)],
        },
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    thread_id = create_resp.json()["id"]

    async with AsyncSessionLocal() as session:
        user = await session.get(User, mentioned_id)
        user.is_active = False
        await session.commit()

    list_resp = await client.get(
        f"/api/v1/briefs/{tenant_a.brief_id}/threads",
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    threads = list_resp.json()
    thread = next(t for t in threads if t["id"] == thread_id)
    mention = thread["comments"][0]["mentions"][0]
    assert mention["is_active"] is False
    assert mention["display_text"] == "Eski Üye"  # frozen at mention time


# ── Annotation reply + brand-side annotation mention creation ───────────────
# (both were confirmed real coverage gaps — only plain `annotation` and only
# agency-side were exercised end-to-end before this.)


async def test_annotation_reply_mention_creates_notification(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    tenant_a, _ = tenants
    mentioned_id = await _add_agency_member(
        tenant_a,
        "Onur Geliştirici",
        AgencyMemberRole.DEVELOPER.value,
        f"onur-reply-{uuid.uuid4().hex[:8]}",
    )

    resp = await client.post(
        f"/api/v1/annotations/{tenant_a.annotation_id}/replies",
        params={"deliverable_id": str(tenant_a.deliverable_id)},
        json={"body": "@Onur bakar mısın, teşekkürler.", "mentioned_user_ids": [str(mentioned_id)]},
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 201
    mentions = resp.json()["mentions"]
    assert [m["mentioned_user_id"] for m in mentions] == [str(mentioned_id)]

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                Mention.__table__.select().where(Mention.source_type == "annotation_reply")
            )
        ).fetchall()
        assert any(str(r.mentioned_user_id) == str(mentioned_id) for r in rows)

        notif = await session.scalar(
            select(Notification).where(Notification.user_id == mentioned_id)
        )
        assert notif is not None


async def test_brand_annotation_create_mentions_agency_member(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    tenant_a, _ = tenants
    assigned_id = await _add_agency_member(
        tenant_a,
        "Atanmış Tasarımcı",
        AgencyMemberRole.DESIGNER.value,
        f"assigned-brand-{uuid.uuid4().hex[:8]}",
    )
    await _assign_to_brief(tenant_a, assigned_id)

    resp = await client.post(
        f"/api/v1/brand-portal/deliverables/{tenant_a.deliverable_id}/annotations",
        json={
            "version_number": 1,
            "annotation_type": "revision",
            "body": "@Atanmış Tasarımcı bu alanı kontrol eder misin?",
            "mentioned_user_ids": [str(assigned_id)],
        },
        headers=brand_headers(tenant_a.brand_manager_token),
    )
    assert resp.status_code == 201
    mentions = resp.json()["mentions"]
    assert [m["mentioned_user_id"] for m in mentions] == [str(assigned_id)]


# ── XSS / adversarial display-name handling ─────────────────────────────────


async def test_display_name_with_script_tag_round_trips_as_inert_text(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    """A malicious full_name is never executed — it's just a string the
    anti-spoofing check matches literally, and the API returns it verbatim
    (JSON-encoded) for the frontend's DOM-based sanitizer to render as text,
    never as HTML markup."""
    tenant_a, _ = tenants
    payload_name = "<script>alert(1)</script>"
    mentioned_id = await _add_agency_member(
        tenant_a, payload_name, AgencyMemberRole.DESIGNER.value, f"xss-{uuid.uuid4().hex[:8]}"
    )

    resp = await client.post(
        f"/api/v1/briefs/{tenant_a.brief_id}/threads",
        json={
            "thread_type": "brief",
            "initial_comment": f"Merhaba {payload_name}, bakar mısın?",
            "visibility": "internal",
            "mentioned_user_ids": [str(mentioned_id)],
        },
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 201
    mentions = resp.json()["comments"][0]["mentions"]
    assert mentions[0]["display_text"] == payload_name  # returned as data, not executed


async def test_display_name_with_event_handler_payload_round_trips_as_inert_text(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    tenant_a, _ = tenants
    payload_name = "img src=x onerror=alert(1)"
    mentioned_id = await _add_agency_member(
        tenant_a, payload_name, AgencyMemberRole.DESIGNER.value, f"xss-evt-{uuid.uuid4().hex[:8]}"
    )

    resp = await client.post(
        f"/api/v1/briefs/{tenant_a.brief_id}/threads",
        json={
            "thread_type": "brief",
            "initial_comment": f"@{payload_name} lütfen bak.",
            "visibility": "internal",
            "mentioned_user_ids": [str(mentioned_id)],
        },
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 201
    mentions = resp.json()["comments"][0]["mentions"]
    assert mentions[0]["display_text"] == payload_name


async def test_fake_mention_markup_in_body_without_id_creates_no_phantom_mention(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    """The backend never parses body text for @-looking markup — only the
    explicit `mentioned_user_ids` list can create a Mention row. Embedded
    fake chip HTML in the body must not fabricate a mention."""
    tenant_a, _ = tenants
    resp = await client.post(
        f"/api/v1/briefs/{tenant_a.brief_id}/threads",
        json={
            "thread_type": "brief",
            "initial_comment": (
                '<span class="mention-chip" data-mention-user-id="'
                f'{uuid.uuid4()}">@Sahte Kullanıcı</span>'
            ),
            "visibility": "internal",
            "mentioned_user_ids": [],
        },
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 201
    assert resp.json()["comments"][0]["mentions"] == []


# ── Spam / caps ───────────────────────────────────────────────────────────────


async def test_more_than_20_mentions_rejected_with_clear_validation_error(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    tenant_a, _ = tenants
    ids = [str(uuid.uuid4()) for _ in range(21)]

    resp = await client.post(
        f"/api/v1/briefs/{tenant_a.brief_id}/threads",
        json={
            "thread_type": "brief",
            "initial_comment": "Çok fazla kişi etiketliyorum.",
            "visibility": "internal",
            "mentioned_user_ids": ids,
        },
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    # Hard rejection (422), not silent truncation — the product rule is a
    # clear error over quietly dropping mentions past the cap.
    assert resp.status_code == 422
    assert "20" in resp.text

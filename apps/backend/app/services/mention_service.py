"""MentionService: the single, durable @mention pipeline.

Replaces the old regex-over-comment-body approach (formerly
``CommentService._dispatch_mentions``). Every comment/annotation/reply
surface in the app funnels through ``sync_mentions_for_source`` so there is
exactly one mention data model and one notification path, never a second
parallel system per feature.
"""

from __future__ import annotations

import unicodedata
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agency_member import AgencyMember
from app.models.brand_member import BrandMember
from app.models.brief import BriefAssignee
from app.models.enums import AgencyMemberRole, AgencyMemberStatus, BrandMemberStatus
from app.models.mention import Mention
from app.models.user import User
from app.schemas.mention import MentionCandidateRead, MentionInline
from app.services.notification_dispatcher import NotificationDispatcher

_AGENCY_ROLE_LABELS: dict[str, str] = {
    AgencyMemberRole.OWNER.value: "Sahip",
    AgencyMemberRole.ADMIN.value: "Yönetici",
    AgencyMemberRole.BRAND_MANAGER.value: "Marka Yöneticisi",
    AgencyMemberRole.DESIGNER.value: "Tasarımcı",
    AgencyMemberRole.DEVELOPER.value: "Geliştirici",
    AgencyMemberRole.SOCIAL_MEDIA_MANAGER.value: "Sosyal Medya Yöneticisi",
    AgencyMemberRole.VIEWER.value: "İzleyici",
}
_BRAND_ROLE_LABELS: dict[str, str] = {
    "brand_owner": "Marka Sahibi",
    "brand_manager": "Marka Yöneticisi",
    "brand_viewer": "İzleyici",
    "external_approver": "Dış Onaylayıcı",
}

_MAX_CANDIDATES = 20


def _normalize(text: str) -> str:
    """Case-fold + strip diacritics so 'İnci'/'inci'/'ınci' all match."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    # Turkish dotless "ı" (U+0131) has no NFKD decomposition and casefolds to
    # itself, not to "i" — fold it explicitly so a query typed without a
    # Turkish keyboard (plain ASCII "i") still matches names containing "ı".
    stripped = stripped.replace("ı", "i")
    return stripped.casefold()


class MentionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Candidates ───────────────────────────────────────────────────────────

    async def get_agency_candidates(
        self,
        *,
        agency_id: uuid.UUID,
        query: str | None,
        exclude_user_id: uuid.UUID | None = None,
    ) -> list[MentionCandidateRead]:
        """Active agency members, excluding the viewer role and the requester.

        Matches §C of the spec: owner/admin/brand_manager/designer/developer/
        social_media_manager are mentionable in agency-side brief comments;
        viewer is not.
        """
        stmt = (
            select(AgencyMember, User)
            .join(User, User.id == AgencyMember.user_id)
            .where(
                AgencyMember.agency_id == agency_id,
                AgencyMember.status == AgencyMemberStatus.ACTIVE.value,
                AgencyMember.deleted_at.is_(None),
                AgencyMember.role != AgencyMemberRole.VIEWER.value,
                User.deleted_at.is_(None),
                User.is_active.is_(True),
            )
        )
        rows = (await self.db.execute(stmt)).all()
        candidates = [
            MentionCandidateRead(
                member_id=member.id,
                user_id=user.id,
                display_name=user.full_name,
                avatar_url=user.avatar_url,
                role_label=_AGENCY_ROLE_LABELS.get(member.role, member.role),
                member_type="agency",
                context_label=None,
            )
            for member, user in rows
            if user.id != exclude_user_id
        ]
        return self._filter_and_cap(candidates, query)

    async def get_brand_candidates(
        self,
        *,
        brand_id: uuid.UUID,
        brief_id: uuid.UUID | None,
        query: str | None,
        exclude_user_id: uuid.UUID | None = None,
    ) -> list[MentionCandidateRead]:
        """Active brand members of this brand, plus agency members who are
        assigned to this specific brief (or, absent assignees, the agency
        owner/admin) — never the whole agency directory (§C)."""
        brand_stmt = (
            select(BrandMember, User)
            .join(User, User.id == BrandMember.user_id)
            .where(
                BrandMember.brand_id == brand_id,
                BrandMember.status == BrandMemberStatus.ACTIVE.value,
                BrandMember.deleted_at.is_(None),
                User.deleted_at.is_(None),
                User.is_active.is_(True),
            )
        )
        brand_rows = (await self.db.execute(brand_stmt)).all()
        candidates = [
            MentionCandidateRead(
                member_id=member.id,
                user_id=user.id,
                display_name=user.full_name,
                avatar_url=user.avatar_url,
                role_label=_BRAND_ROLE_LABELS.get(member.role, member.role),
                member_type="brand",
                context_label=None,
            )
            for member, user in brand_rows
            if user.id != exclude_user_id
        ]

        agency_user_ids: set[uuid.UUID] = set()
        if brief_id is not None:
            assignee_stmt = (
                select(AgencyMember, User)
                .join(User, User.id == AgencyMember.user_id)
                .join(BriefAssignee, BriefAssignee.user_id == User.id)
                .where(
                    BriefAssignee.brief_id == brief_id,
                    AgencyMember.status == AgencyMemberStatus.ACTIVE.value,
                    AgencyMember.deleted_at.is_(None),
                    User.deleted_at.is_(None),
                    User.is_active.is_(True),
                )
            )
            for member, user in (await self.db.execute(assignee_stmt)).all():
                if user.id == exclude_user_id or user.id in agency_user_ids:
                    continue
                agency_user_ids.add(user.id)
                candidates.append(
                    MentionCandidateRead(
                        member_id=member.id,
                        user_id=user.id,
                        display_name=user.full_name,
                        avatar_url=user.avatar_url,
                        role_label=_AGENCY_ROLE_LABELS.get(member.role, member.role),
                        member_type="agency",
                        context_label="Ajans Ekibi",
                    )
                )

        # Always allow reaching the agency owner/admin, even with no assignees
        # yet — resolved via the brand's own agency_id, not the brand_members
        # join (which would only prove brand membership rows exist).
        from app.models.brand import Brand

        brand = await self.db.get(Brand, brand_id)
        if brand is not None:
            owner_admin_stmt = (
                select(AgencyMember, User)
                .join(User, User.id == AgencyMember.user_id)
                .where(
                    AgencyMember.agency_id == brand.agency_id,
                    AgencyMember.role.in_(
                        [AgencyMemberRole.OWNER.value, AgencyMemberRole.ADMIN.value]
                    ),
                    AgencyMember.status == AgencyMemberStatus.ACTIVE.value,
                    AgencyMember.deleted_at.is_(None),
                    User.deleted_at.is_(None),
                    User.is_active.is_(True),
                )
            )
            for member, user in (await self.db.execute(owner_admin_stmt)).all():
                if user.id == exclude_user_id or user.id in agency_user_ids:
                    continue
                agency_user_ids.add(user.id)
                candidates.append(
                    MentionCandidateRead(
                        member_id=member.id,
                        user_id=user.id,
                        display_name=user.full_name,
                        avatar_url=user.avatar_url,
                        role_label=_AGENCY_ROLE_LABELS.get(member.role, member.role),
                        member_type="agency",
                        context_label="Ajans Ekibi",
                    )
                )

        return self._filter_and_cap(candidates, query)

    def _filter_and_cap(
        self, candidates: list[MentionCandidateRead], query: str | None
    ) -> list[MentionCandidateRead]:
        if query:
            needle = _normalize(query)
            candidates = [c for c in candidates if needle in _normalize(c.display_name)]
        candidates.sort(key=lambda c: c.display_name.casefold())
        return candidates[:_MAX_CANDIDATES]

    # ── Read (display) ──────────────────────────────────────────────────────

    async def get_inline_mentions(
        self, *, source_type: str, source_id: uuid.UUID
    ) -> list[MentionInline]:
        """Mentions to embed on a CommentRead/AnnotationRead so the frontend
        can render chips without a second round-trip. ``is_active`` reflects
        *right now*, not at mention time — a removed team member still shows
        their frozen ``display_text``, but the frontend uses ``is_active`` to
        render the "Eski ekip üyesi" fallback instead of a live profile link.
        """
        stmt = select(Mention).where(
            Mention.source_type == source_type,
            Mention.source_id == source_id,
            Mention.deleted_at.is_(None),
        )
        rows = list((await self.db.execute(stmt)).scalars().all())
        if not rows:
            return []

        user_ids = {m.mentioned_user_id for m in rows}
        active_stmt = select(User.id).where(
            User.id.in_(user_ids), User.deleted_at.is_(None), User.is_active.is_(True)
        )
        active_ids = {row[0] for row in (await self.db.execute(active_stmt)).all()}

        return [
            MentionInline(
                mentioned_user_id=m.mentioned_user_id,
                display_text=m.display_text,
                is_active=m.mentioned_user_id in active_ids,
            )
            for m in rows
        ]

    # ── Sync (create/edit) ───────────────────────────────────────────────────

    async def sync_mentions_for_source(
        self,
        *,
        agency_id: uuid.UUID,
        brand_id: uuid.UUID | None,
        brief_id: uuid.UUID | None,
        deliverable_id: uuid.UUID | None,
        source_type: str,
        source_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        actor_name: str,
        body_text: str,
        mentioned_user_ids: list[uuid.UUID],
        portal: str,
        notification_event_type: str,
        notification_payload_extra: dict,
    ) -> list[uuid.UUID]:
        """Validate + persist mentions for one comment/annotation/reply, then
        notify only the *newly* mentioned users (dedup on edit). Returns the
        list of user ids that were actually notified.
        """
        # 1) Resolve the real candidate set for this context — never trust
        #    the client's id list without re-deriving who is allowed here.
        if portal == "agency":
            candidates = await self.get_agency_candidates(
                agency_id=agency_id, query=None, exclude_user_id=None
            )
        else:
            candidates = await self.get_brand_candidates(
                brand_id=brand_id, brief_id=brief_id, query=None, exclude_user_id=None
            )
        candidate_by_user_id = {c.user_id: c for c in candidates}

        normalized_body = _normalize(body_text)
        validated: dict[uuid.UUID, str] = {}
        for uid in dict.fromkeys(mentioned_user_ids):  # de-dupe, preserve order
            if uid == actor_user_id:
                continue  # self-mention never notifies
            candidate = candidate_by_user_id.get(uid)
            if candidate is None:
                continue  # not a valid candidate in this tenant/context — dropped silently
            # Anti-spoofing: require the person's name (or its first token)
            # to actually appear in the submitted text, not just its ID.
            first_token = candidate.display_name.split(" ")[0]
            if _normalize(first_token) not in normalized_body:
                continue
            validated[uid] = candidate.display_name

        # 2) Diff against existing live mentions for this exact source row —
        #    re-typing the same mention on edit must not re-notify (dedupe),
        #    and dropping a mention on edit must retract it (soft-delete).
        existing_stmt = select(Mention).where(
            Mention.source_type == source_type,
            Mention.source_id == source_id,
            Mention.deleted_at.is_(None),
        )
        existing_rows = list((await self.db.execute(existing_stmt)).scalars().all())
        existing_by_user = {m.mentioned_user_id: m for m in existing_rows}

        new_user_ids = [uid for uid in validated if uid not in existing_by_user]
        removed_user_ids = [uid for uid in existing_by_user if uid not in validated]

        for uid in removed_user_ids:
            existing_by_user[uid].soft_delete()

        for uid in new_user_ids:
            candidate = candidate_by_user_id[uid]
            self.db.add(
                Mention(
                    agency_id=agency_id,
                    brand_id=brand_id,
                    mentioned_user_id=uid,
                    mentioned_agency_member_id=(
                        candidate.member_id if candidate.member_type == "agency" else None
                    ),
                    mentioned_brand_member_id=(
                        candidate.member_id if candidate.member_type == "brand" else None
                    ),
                    actor_user_id=actor_user_id,
                    source_type=source_type,
                    source_id=source_id,
                    brief_id=brief_id,
                    deliverable_id=deliverable_id,
                    display_text=candidate.display_name,
                )
            )

        if not new_user_ids:
            return []

        await self.db.flush()

        payload = {"actor_name": actor_name, **notification_payload_extra}
        dispatcher = NotificationDispatcher(self.db)
        await dispatcher.emit(
            notification_event_type,
            payload=payload,
            agency_id=agency_id,
            brand_id=brand_id,
            actor_user_id=actor_user_id,
            recipient_ids=new_user_ids,
        )
        return new_user_ids


__all__ = ["MentionService"]

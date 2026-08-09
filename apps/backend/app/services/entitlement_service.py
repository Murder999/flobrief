"""EntitlementService — server-side feature limit enforcement.

All public methods raise HTTP 403 when a limit is hit.
No frontend-only locking is sufficient.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.brand import Brand
from app.models.brand_member import BrandMember
from app.models.brief_template import BriefTemplate
from app.models.entitlement_override import EntitlementOverride
from app.models.enums import AgencyMemberStatus, BrandMemberStatus, BrandStatus, SubscriptionStatus
from app.models.invitation import Invitation
from app.models.plan import Plan
from app.models.subscription import Subscription

_403 = status.HTTP_403_FORBIDDEN
_402 = status.HTTP_402_PAYMENT_REQUIRED

_UNSET = object()  # sentinel: "no override row" vs. an override explicitly set to None (unlimited)


class EntitlementService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def get_plan(self, agency_id: uuid.UUID) -> Plan | None:
        """Return active plan for agency; None if no active subscription."""
        result = await self.db.execute(
            select(Plan)
            .join(Subscription, Subscription.plan_id == Plan.id)
            .where(
                Subscription.agency_id == agency_id,
                Subscription.deleted_at.is_(None),
                Subscription.status.in_(
                    [
                        SubscriptionStatus.TRIALING.value,
                        SubscriptionStatus.ACTIVE.value,
                        SubscriptionStatus.PAST_DUE.value,
                    ]
                ),
                Plan.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def _count_active_brands(self, agency_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count(Brand.id)).where(
                Brand.agency_id == agency_id,
                Brand.status == BrandStatus.ACTIVE.value,
                Brand.deleted_at.is_(None),
            )
        )
        return result.scalar_one() or 0

    async def _count_active_members(self, agency_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count(AgencyMember.id)).where(
                AgencyMember.agency_id == agency_id,
                AgencyMember.status == AgencyMemberStatus.ACTIVE.value,
                AgencyMember.deleted_at.is_(None),
            )
        )
        return result.scalar_one() or 0

    async def _count_templates(self, agency_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count(BriefTemplate.id)).where(
                BriefTemplate.agency_id == agency_id,
                BriefTemplate.deleted_at.is_(None),
            )
        )
        return result.scalar_one() or 0

    async def _count_active_brand_members(self, brand_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count(BrandMember.id)).where(
                BrandMember.brand_id == brand_id,
                BrandMember.status == BrandMemberStatus.ACTIVE.value,
                BrandMember.deleted_at.is_(None),
            )
        )
        return result.scalar_one() or 0

    async def _count_pending_agency_invites(self, agency_id: uuid.UUID) -> int:
        now = func.now()
        result = await self.db.execute(
            select(func.count(Invitation.id)).where(
                Invitation.agency_id == agency_id,
                Invitation.invitation_type == "agency",
                Invitation.accepted_at.is_(None),
                Invitation.revoked_at.is_(None),
                Invitation.rejected_at.is_(None),
                Invitation.deleted_at.is_(None),
                Invitation.expires_at > now,
            )
        )
        return result.scalar_one() or 0

    async def _count_pending_brand_invites(self, brand_id: uuid.UUID) -> int:
        now = func.now()
        result = await self.db.execute(
            select(func.count(Invitation.id)).where(
                Invitation.brand_id == brand_id,
                Invitation.invitation_type == "brand",
                Invitation.accepted_at.is_(None),
                Invitation.revoked_at.is_(None),
                Invitation.rejected_at.is_(None),
                Invitation.deleted_at.is_(None),
                Invitation.expires_at > now,
            )
        )
        return result.scalar_one() or 0

    async def _resolve_limit(
        self,
        *,
        agency_id: uuid.UUID | None,
        brand_id: uuid.UUID | None,
        limit_key: str,
        plan_value: int | None,
    ) -> int | None:
        """Override (including explicit-NULL-for-unlimited) always wins over the plan value."""
        result = await self.db.execute(
            select(EntitlementOverride.limit_value).where(
                EntitlementOverride.limit_key == limit_key,
                EntitlementOverride.deleted_at.is_(None),
                EntitlementOverride.agency_id == agency_id
                if brand_id is None
                else EntitlementOverride.brand_id == brand_id,
            )
        )
        row = result.first()
        if row is None:
            return plan_value
        return row[0]

    async def _lock_agency(self, agency_id: uuid.UUID) -> None:
        await self.db.execute(select(Agency.id).where(Agency.id == agency_id).with_for_update())

    async def _lock_brand(self, brand_id: uuid.UUID) -> None:
        await self.db.execute(select(Brand.id).where(Brand.id == brand_id).with_for_update())

    # ── Limit checks ──────────────────────────────────────────────────────────

    async def check_brand_limit(self, agency_id: uuid.UUID) -> None:
        plan = await self.get_plan(agency_id)
        if plan is None or plan.max_brands is None:
            return  # No plan or unlimited
        current = await self._count_active_brands(agency_id)
        if current >= plan.max_brands:
            raise HTTPException(
                _403,
                f"Plan limitine ulaştınız: maksimum {plan.max_brands} marka. "
                "Planınızı yükselterek daha fazla marka ekleyebilirsiniz.",
            )

    async def check_user_limit(self, agency_id: uuid.UUID, *, lock: bool = False) -> None:
        if lock:
            await self._lock_agency(agency_id)
        plan = await self.get_plan(agency_id)
        plan_limit = plan.max_users if plan else None
        limit = await self._resolve_limit(
            agency_id=agency_id, brand_id=None, limit_key="max_users", plan_value=plan_limit
        )
        if limit is None:
            return
        active = await self._count_active_members(agency_id)
        pending = await self._count_pending_agency_invites(agency_id)
        used = active + pending
        if used >= limit:
            raise HTTPException(
                _403,
                {
                    "message": (
                        f"Plan limitine ulaştınız: maksimum {limit} ajans kullanıcısı. "
                        "Planınızı yükselterek daha fazla üye ekleyebilirsiniz."
                    ),
                    "limit_key": "max_users",
                    "used": used,
                    "limit": limit,
                },
            )

    async def check_brand_user_limit(
        self, agency_id: uuid.UUID, brand_id: uuid.UUID, *, lock: bool = False
    ) -> None:
        if lock:
            await self._lock_brand(brand_id)
        plan = await self.get_plan(agency_id)
        plan_limit = plan.max_brand_users if plan else None
        limit = await self._resolve_limit(
            agency_id=None, brand_id=brand_id, limit_key="max_brand_users", plan_value=plan_limit
        )
        if limit is None:
            return
        active = await self._count_active_brand_members(brand_id)
        pending = await self._count_pending_brand_invites(brand_id)
        used = active + pending
        if used >= limit:
            raise HTTPException(
                _403,
                {
                    "message": (
                        f"Plan limitine ulaştınız: maksimum {limit} marka kullanıcısı. "
                        "Planınızı yükselterek daha fazla üye ekleyebilirsiniz."
                    ),
                    "limit_key": "max_brand_users",
                    "used": used,
                    "limit": limit,
                },
            )

    async def check_pending_invite_limit(
        self,
        agency_id: uuid.UUID,
        brand_id: uuid.UUID | None = None,
        *,
        lock: bool = False,
    ) -> None:
        """Independent cap on outstanding invitations, separate from the seat count."""
        if brand_id is None:
            if lock:
                await self._lock_agency(agency_id)
            plan = await self.get_plan(agency_id)
            plan_limit = plan.max_pending_agency_invites if plan else None
            limit = await self._resolve_limit(
                agency_id=agency_id,
                brand_id=None,
                limit_key="max_pending_agency_invites",
                plan_value=plan_limit,
            )
            if limit is None:
                return
            used = await self._count_pending_agency_invites(agency_id)
            limit_key = "max_pending_agency_invites"
        else:
            if lock:
                await self._lock_brand(brand_id)
            plan = await self.get_plan(agency_id)
            plan_limit = plan.max_pending_brand_invites if plan else None
            limit = await self._resolve_limit(
                agency_id=None,
                brand_id=brand_id,
                limit_key="max_pending_brand_invites",
                plan_value=plan_limit,
            )
            if limit is None:
                return
            used = await self._count_pending_brand_invites(brand_id)
            limit_key = "max_pending_brand_invites"

        if used >= limit:
            raise HTTPException(
                _403,
                {
                    "message": (
                        f"Bekleyen davet limitine ulaştınız: maksimum {limit}. "
                        "Yeni davet göndermeden önce bekleyen davetleri iptal edin."
                    ),
                    "limit_key": limit_key,
                    "used": used,
                    "limit": limit,
                },
            )

    async def check_template_limit(self, agency_id: uuid.UUID) -> None:
        plan = await self.get_plan(agency_id)
        if plan is None or plan.max_brief_templates is None:
            return
        current = await self._count_templates(agency_id)
        if current >= plan.max_brief_templates:
            raise HTTPException(
                _403,
                f"Plan limitine ulaştınız: maksimum {plan.max_brief_templates} şablon. "
                "Planınızı yükselterek daha fazla şablon oluşturabilirsiniz.",
            )

    async def check_feature(self, agency_id: uuid.UUID, feature: str) -> None:
        """Raise 403 if the feature is not enabled on the agency's plan.

        feature: 'white_label_enabled' | 'advanced_reporting_enabled' |
                 'pdf_export_enabled' | 'public_report_link_enabled' |
                 'whatsapp_infrastructure_enabled'
        """
        plan = await self.get_plan(agency_id)
        if plan is None:
            raise HTTPException(_403, "Bu özellik mevcut planınızda bulunmuyor.")
        if not getattr(plan, feature, False):
            readable = feature.replace("_enabled", "").replace("_", " ").title()
            raise HTTPException(
                _403,
                f"'{readable}' özelliği mevcut planınızda aktif değil. "
                "Daha üst bir plana geçerek bu özelliği kullanabilirsiniz.",
            )

    # ── Brand-scoped usage summary ──────────────────────────────────────────────

    async def get_brand_usage_summary(self, agency_id: uuid.UUID, brand_id: uuid.UUID) -> dict:
        """Current seat/invite usage vs. limits for one brand's team page."""
        plan = await self.get_plan(agency_id)
        user_limit = await self._resolve_limit(
            agency_id=None,
            brand_id=brand_id,
            limit_key="max_brand_users",
            plan_value=plan.max_brand_users if plan else None,
        )
        invite_limit = await self._resolve_limit(
            agency_id=None,
            brand_id=brand_id,
            limit_key="max_pending_brand_invites",
            plan_value=plan.max_pending_brand_invites if plan else None,
        )
        active = await self._count_active_brand_members(brand_id)
        pending = await self._count_pending_brand_invites(brand_id)
        return {
            "plan_code": plan.code if plan else None,
            "plan_name": plan.name if plan else None,
            "users": {
                "used": active + pending,
                "active": active,
                "pending_invites": pending,
                "limit": user_limit,
                "available": None if user_limit is None else max(user_limit - active - pending, 0),
            },
            "pending_invites": {
                "used": pending,
                "limit": invite_limit,
            },
        }

    # ── Usage summary ─────────────────────────────────────────────────────────

    async def get_usage_summary(self, agency_id: uuid.UUID) -> dict:
        """Returns current usage vs limits for all metered entitlements."""
        plan = await self.get_plan(agency_id)
        brands = await self._count_active_brands(agency_id)
        members = await self._count_active_members(agency_id)
        pending_invites = await self._count_pending_agency_invites(agency_id)
        templates = await self._count_templates(agency_id)
        user_limit = await self._resolve_limit(
            agency_id=agency_id,
            brand_id=None,
            limit_key="max_users",
            plan_value=plan.max_users if plan else None,
        )

        return {
            "plan_code": plan.code if plan else None,
            "plan_name": plan.name if plan else None,
            "brands": {
                "used": brands,
                "limit": plan.max_brands if plan else None,
            },
            "users": {
                "used": members + pending_invites,
                "active": members,
                "pending_invites": pending_invites,
                "limit": user_limit,
            },
            "brief_templates": {
                "used": templates,
                "limit": plan.max_brief_templates if plan else None,
            },
            "storage_gb": {
                "used": 0,  # Storage tracking deferred to Part 15
                "limit": plan.max_storage_gb if plan else None,
            },
            "features": {
                "white_label_enabled": plan.white_label_enabled if plan else False,
                "advanced_reporting_enabled": plan.advanced_reporting_enabled if plan else False,
                "pdf_export_enabled": plan.pdf_export_enabled if plan else False,
                "public_report_link_enabled": plan.public_report_link_enabled if plan else False,
                "whatsapp_infrastructure_enabled": (
                    plan.whatsapp_infrastructure_enabled if plan else False
                ),
            },
        }

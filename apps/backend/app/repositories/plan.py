from __future__ import annotations

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PlanCode
from app.models.plan import Plan

PUBLIC_PLAN_ORDER = (
    PlanCode.BRAND_SOLO.value,
    PlanCode.STARTER_AGENCY.value,
    PlanCode.PRO_AGENCY.value,
    PlanCode.AGENCY_PLUS.value,
    PlanCode.ENTERPRISE.value,
)


class PlanRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_active(self) -> list[Plan]:
        result = await self.db.execute(
            select(Plan)
            .where(Plan.deleted_at.is_(None), Plan.is_active.is_(True))
            .order_by(
                case(
                    {code: position for position, code in enumerate(PUBLIC_PLAN_ORDER)},
                    value=Plan.code,
                    else_=len(PUBLIC_PLAN_ORDER),
                ),
                Plan.monthly_price_cents.asc(),
            )
        )
        return list(result.scalars().all())

    async def get_by_id(self, plan_id: object) -> Plan | None:
        result = await self.db.execute(
            select(Plan).where(Plan.id == plan_id, Plan.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Plan | None:
        result = await self.db.execute(
            select(Plan).where(Plan.code == code, Plan.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def upsert_plan(self, data: dict) -> Plan:
        existing = await self.get_by_code(data["code"])
        if existing:
            for key, value in data.items():
                if key != "code":
                    setattr(existing, key, value)
            self.db.add(existing)
            return existing
        plan = Plan(**data)
        self.db.add(plan)
        await self.db.flush()
        await self.db.refresh(plan)
        return plan

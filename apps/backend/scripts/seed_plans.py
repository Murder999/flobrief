#!/usr/bin/env python3
"""Flobrief Plan Seed Script.

Seeds the five plan definitions. Idempotent: safe to run multiple times.
Existing plans (matched by code) are updated in place; missing ones are created.

Usage (run from apps/backend/):
    python scripts/seed_plans.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.enums import PlanCode  # noqa: E402
from app.models.plan import Plan  # noqa: E402

PLAN_DEFINITIONS = [
    {
        "code": PlanCode.STARTER_AGENCY.value,
        "name": "Starter Agency",
        "description": "Small agencies getting started with brief management.",
        "monthly_price_cents": 4900,
        "yearly_price_cents": 46800,
        "currency": "USD",
        "max_brands": 5,
        "max_users": 10,
        "max_brief_templates": 25,
        "max_storage_gb": 25,
        "white_label_enabled": False,
        "advanced_reporting_enabled": True,
        "pdf_export_enabled": True,
        "public_report_link_enabled": True,
        "whatsapp_infrastructure_enabled": False,
        "platform_admin_visible": True,
        "is_active": True,
    },
    {
        "code": PlanCode.PRO_AGENCY.value,
        "name": "Pro Agency",
        "description": "Growing agencies with multiple brands and team members.",
        "monthly_price_cents": 9900,
        "yearly_price_cents": 94800,
        "currency": "USD",
        "max_brands": 15,
        "max_users": 25,
        "max_brief_templates": None,
        "max_storage_gb": 50,
        "white_label_enabled": False,
        "advanced_reporting_enabled": True,
        "pdf_export_enabled": True,
        "public_report_link_enabled": True,
        "whatsapp_infrastructure_enabled": True,
        "platform_admin_visible": True,
        "is_active": True,
    },
    {
        "code": PlanCode.AGENCY_PLUS.value,
        "name": "Agency Plus",
        "description": "Full-featured plan with white-label and WhatsApp integration.",
        "monthly_price_cents": 19900,
        "yearly_price_cents": 190800,
        "currency": "USD",
        "max_brands": None,
        "max_users": None,
        "max_brief_templates": None,
        "max_storage_gb": 200,
        "white_label_enabled": True,
        "advanced_reporting_enabled": True,
        "pdf_export_enabled": True,
        "public_report_link_enabled": True,
        "whatsapp_infrastructure_enabled": True,
        "platform_admin_visible": True,
        "is_active": True,
    },
    {
        "code": PlanCode.BRAND_SOLO.value,
        "name": "Brand Solo",
        "description": "For independent brands managing their own creative briefs.",
        "monthly_price_cents": 1900,
        "yearly_price_cents": 18000,
        "currency": "USD",
        "max_brands": 1,
        "max_users": 5,
        "max_brief_templates": 10,
        "max_storage_gb": 10,
        "white_label_enabled": False,
        "advanced_reporting_enabled": False,
        "pdf_export_enabled": True,
        "public_report_link_enabled": False,
        "whatsapp_infrastructure_enabled": False,
        "platform_admin_visible": True,
        "is_active": True,
    },
    {
        "code": PlanCode.ENTERPRISE.value,
        "name": "Enterprise",
        "description": "Custom plan for large agencies with unlimited resources and dedicated support.",  # noqa: E501
        "monthly_price_cents": 0,
        "yearly_price_cents": 0,
        "currency": "USD",
        "max_brands": None,
        "max_users": None,
        "max_brief_templates": None,
        "max_storage_gb": None,
        "white_label_enabled": True,
        "advanced_reporting_enabled": True,
        "pdf_export_enabled": True,
        "public_report_link_enabled": True,
        "whatsapp_infrastructure_enabled": True,
        "platform_admin_visible": True,
        "is_active": True,
    },
]


async def seed_plans() -> None:
    async with AsyncSessionLocal() as session:
        created = 0
        updated = 0
        for plan_data in PLAN_DEFINITIONS:
            result = await session.execute(select(Plan).where(Plan.code == plan_data["code"]))
            plan = result.scalar_one_or_none()
            if plan is not None:
                for field, value in plan_data.items():
                    if field == "code":
                        continue
                    setattr(plan, field, value)
                updated += 1
            else:
                session.add(Plan(**plan_data))
                created += 1
        await session.commit()

    print(f"[OK] Plans seeded: {created} created, {updated} updated.")


if __name__ == "__main__":
    asyncio.run(seed_plans())

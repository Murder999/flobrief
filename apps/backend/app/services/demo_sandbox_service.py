from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.brand_member import BrandMember
from app.models.demo_sandbox import DemoSandbox, PlatformDemoSettings
from app.models.enums import (
    AgencyMemberRole,
    AgencyMemberStatus,
    AgencyStatus,
    BillingProvider,
    BrandMemberRole,
    BrandMemberStatus,
    PlanCode,
    SubscriptionStatus,
    UserType,
)
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.models.user_token import UserToken
from app.services.demo_sandbox_seed import seed_demo_workspace
from app.services.token_service import (
    TOKEN_TYPE_REFRESH,
    generate_token,
    hash_token,
    new_token_family,
)


def hash_demo_ip(ip_address: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        ip_address.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


async def get_demo_settings(
    db: AsyncSession, *, create: bool = False, lock: bool = False
) -> PlatformDemoSettings | None:
    stmt = select(PlatformDemoSettings).where(
        PlatformDemoSettings.setting_key == "default",
        PlatformDemoSettings.deleted_at.is_(None),
    )
    if lock:
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None and create:
        row = PlatformDemoSettings(setting_key="default")
        db.add(row)
        await db.flush()
    return row


async def demo_counts(db: AsyncSession) -> tuple[int, int, int]:
    now = datetime.now(UTC)
    active = await db.scalar(
        select(func.count(DemoSandbox.id)).where(
            DemoSandbox.status == "active",
            DemoSandbox.expires_at > now,
            DemoSandbox.deleted_at.is_(None),
        )
    )
    total = await db.scalar(
        select(func.count(DemoSandbox.id)).where(DemoSandbox.deleted_at.is_(None))
    )
    return int(active or 0), int(total or 0), int((total or 0) - (active or 0))


async def verify_turnstile(token: str, remote_ip: str) -> bool:
    if not settings.DEMO_SANDBOX_TURNSTILE_SECRET_KEY:
        return False
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={
                    "secret": settings.DEMO_SANDBOX_TURNSTILE_SECRET_KEY,
                    "response": token,
                    "remoteip": remote_ip,
                },
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        return False
    return payload.get("success") is True


class DemoSandboxService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        *,
        ip_address: str,
        user_agent: str | None,
        turnstile_token: str | None,
    ) -> tuple[DemoSandbox, str, str]:
        config = await get_demo_settings(self.db, create=True, lock=True)
        assert config is not None
        if not config.enabled:
            raise HTTPException(status.HTTP_409_CONFLICT, "Demo sandbox şu anda kapalı")

        if config.captcha_required and (
            not turnstile_token or not await verify_turnstile(turnstile_token, ip_address)
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Güvenlik doğrulaması tamamlanamadı",
            )

        now = datetime.now(UTC)
        active_count, _, _ = await demo_counts(self.db)
        if active_count >= config.max_active_sandboxes:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Demo kapasitesi şu anda dolu. Lütfen daha sonra tekrar deneyin.",
                headers={"Retry-After": "900"},
            )

        ip_hash = hash_demo_ip(ip_address)
        created_from_ip = await self.db.scalar(
            select(func.count(DemoSandbox.id)).where(
                DemoSandbox.ip_hash == ip_hash,
                DemoSandbox.created_at >= now - timedelta(days=1),
                DemoSandbox.deleted_at.is_(None),
            )
        )
        if int(created_from_ip or 0) >= config.max_creations_per_ip_per_day:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Günlük demo oluşturma sınırına ulaştınız.",
                headers={"Retry-After": "86400"},
            )

        suffix = secrets.token_hex(6)
        expires_at = now + timedelta(hours=config.duration_hours)
        plan = await self.db.scalar(
            select(Plan).where(
                Plan.code == PlanCode.PRO_AGENCY.value,
                Plan.deleted_at.is_(None),
            )
        )

        user = User(
            email=f"demo-{suffix}@sandbox.flobrief.invalid",
            password_hash=hash_password(secrets.token_urlsafe(32)),
            full_name="Demo Kullanıcısı",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
            job_title="Ajans Yöneticisi",
        )
        self.db.add(user)
        await self.db.flush()

        agency = Agency(
            name=f"PostPiloter Demo · {suffix[:6].upper()}",
            slug=f"demo-{suffix}",
            status=AgencyStatus.ACTIVE.value,
            owner_user_id=user.id,
            plan_id=plan.id if plan else None,
            is_demo=True,
            demo_started_at=now,
            demo_expires_at=expires_at,
        )
        self.db.add(agency)
        await self.db.flush()
        self.db.add(
            AgencyMember(
                agency_id=agency.id,
                user_id=user.id,
                role=AgencyMemberRole.OWNER.value,
                status=AgencyMemberStatus.ACTIVE.value,
                joined_at=now,
            )
        )

        brand_user = User(
            email=f"demo-brand-{suffix}@sandbox.flobrief.invalid",
            password_hash=hash_password(secrets.token_urlsafe(32)),
            full_name="Demo Marka Kullanıcısı",
            user_type=UserType.BRAND_USER.value,
            is_active=False,
            is_verified=True,
            job_title="Marka Yöneticisi",
        )
        self.db.add(brand_user)
        await self.db.flush()

        if plan is not None:
            self.db.add(
                Subscription(
                    agency_id=agency.id,
                    plan_id=plan.id,
                    status=SubscriptionStatus.ACTIVE.value,
                    billing_provider=BillingProvider.MANUAL.value,
                    current_period_start=now,
                    current_period_end=expires_at,
                    cancel_at_period_end=True,
                )
            )

        sandbox = DemoSandbox(
            agency_id=agency.id,
            owner_user_id=user.id,
            brand_user_id=brand_user.id,
            status="active",
            expires_at=expires_at,
            ip_hash=ip_hash,
            user_agent=(user_agent or "")[:1000] or None,
        )
        self.db.add(sandbox)
        demo_brand = await seed_demo_workspace(
            self.db,
            agency_id=agency.id,
            owner_user_id=user.id,
        )
        self.db.add(
            BrandMember(
                brand_id=demo_brand.id,
                user_id=brand_user.id,
                role=BrandMemberRole.BRAND_MANAGER.value,
                status=BrandMemberStatus.ACTIVE.value,
                joined_at=now,
            )
        )

        refresh_plaintext = generate_token()
        token_family = new_token_family()
        self.db.add(
            UserToken(
                user_id=user.id,
                token_hash=hash_token(refresh_plaintext),
                token_family=token_family,
                token_type=TOKEN_TYPE_REFRESH,
                expires_at=expires_at,
                ip_address=ip_address,
                user_agent=(user_agent or "")[:1000] or None,
            )
        )
        user.last_login_at = now
        await self.db.commit()
        await self.db.refresh(sandbox)

        access_expires_at = min(
            now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
            sandbox.expires_at,
        )
        access_token = create_access_token(
            subject=str(user.id),
            extra_claims={
                "user_type": user.user_type,
                "demo": True,
                "demo_session_id": str(token_family),
            },
            expires_at=access_expires_at,
        )
        return sandbox, access_token, refresh_plaintext

    async def terminate(
        self,
        sandbox: DemoSandbox,
        *,
        reason: str,
    ) -> None:
        if sandbox.status != "active":
            return
        now = datetime.now(UTC)
        sandbox.status = "expired" if reason == "expired" else "terminated"
        sandbox.terminated_at = now
        sandbox.termination_reason = reason

        agency = await self.db.get(Agency, sandbox.agency_id)
        if agency is not None:
            agency.status = AgencyStatus.SUSPENDED.value
            agency.demo_expires_at = min(agency.demo_expires_at or now, now)
            self.db.add(agency)

        user_ids = [sandbox.owner_user_id]
        if sandbox.brand_user_id is not None:
            user_ids.append(sandbox.brand_user_id)
        users = (await self.db.execute(select(User).where(User.id.in_(user_ids)))).scalars()
        for user in users:
            user.is_active = False
            self.db.add(user)

        await self.db.execute(
            update(UserToken)
            .where(
                UserToken.user_id.in_(user_ids),
                UserToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        self.db.add(sandbox)


async def terminate_expired_sandboxes(db: AsyncSession, *, batch_size: int = 100) -> int:
    now = datetime.now(UTC)
    result = await db.execute(
        select(DemoSandbox)
        .where(
            DemoSandbox.status == "active",
            DemoSandbox.expires_at <= now,
            DemoSandbox.deleted_at.is_(None),
        )
        .order_by(DemoSandbox.expires_at.asc())
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    rows = list(result.scalars().all())
    service = DemoSandboxService(db)
    for row in rows:
        await service.terminate(row, reason="expired")
    if rows:
        await db.commit()
    return len(rows)

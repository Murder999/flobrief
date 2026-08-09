"""
Dev script — create a brand user and wire them to a brand.

Usage (from apps/backend/):
    python ../../scripts/create_brand_user.py \
        --agency-name "Deneme Ajans" \
        --brand-name "VEXX" \
        --email "efe@vexx.com" \
        --full-name "Efe VEXX" \
        --password "159951.Efe."
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
import os

# Allow running from the repo root or apps/backend/
_backend = os.path.join(os.path.dirname(__file__), "..", "apps", "backend")
if os.path.isdir(_backend):
    sys.path.insert(0, os.path.abspath(_backend))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.agency import Agency  # noqa: E402
from app.models.brand import Brand  # noqa: E402
from app.models.brand_member import BrandMember  # noqa: E402
from app.models.enums import AgencyStatus, BrandMemberRole, BrandMemberStatus, UserType  # noqa: E402
from app.models.user import User  # noqa: E402


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:90] or "brand"


async def run(
    agency_name: str,
    brand_name: str,
    email: str,
    full_name: str,
    password: str,
) -> None:
    async with AsyncSessionLocal() as db:
        await _create(db, agency_name, brand_name, email, full_name, password)
        await db.commit()


async def _create(
    db: AsyncSession,
    agency_name: str,
    brand_name: str,
    email: str,
    full_name: str,
    password: str,
) -> None:
    # ── 1. Agency ──────────────────────────────────────────────────────────────
    agency_slug = _slug(agency_name)
    result = await db.execute(
        select(Agency).where(Agency.name == agency_name, Agency.deleted_at.is_(None))
    )
    agency = result.scalar_one_or_none()
    if agency is None:
        # Try by slug
        result = await db.execute(
            select(Agency).where(Agency.slug == agency_slug, Agency.deleted_at.is_(None))
        )
        agency = result.scalar_one_or_none()

    if agency is None:
        agency = Agency(
            name=agency_name,
            slug=agency_slug,
            status=AgencyStatus.ACTIVE.value,
        )
        db.add(agency)
        await db.flush()
        await db.refresh(agency)
        print(f"[+] Ajans oluşturuldu: {agency.name} ({agency.id})")
    else:
        print(f"[=] Ajans bulundu: {agency.name} ({agency.id})")

    # ── 2. Brand ───────────────────────────────────────────────────────────────
    brand_slug = _slug(brand_name)
    result = await db.execute(
        select(Brand).where(
            Brand.agency_id == agency.id,
            Brand.name == brand_name,
            Brand.deleted_at.is_(None),
        )
    )
    brand = result.scalar_one_or_none()
    if brand is None:
        # Try unique slug with counter
        candidate = brand_slug
        counter = 1
        while True:
            exists = await db.execute(
                select(Brand).where(Brand.slug == candidate, Brand.deleted_at.is_(None))
            )
            if exists.scalar_one_or_none() is None:
                break
            candidate = f"{brand_slug}-{counter}"
            counter += 1

        brand = Brand(
            agency_id=agency.id,
            name=brand_name,
            slug=candidate,
        )
        db.add(brand)
        await db.flush()
        await db.refresh(brand)
        print(f"[+] Marka oluşturuldu: {brand.name} ({brand.id})")
    else:
        print(f"[=] Marka bulundu: {brand.name} ({brand.id})")

    # ── 3. User ────────────────────────────────────────────────────────────────
    result = await db.execute(
        select(User).where(User.email == email.lower(), User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            email=email.lower().strip(),
            full_name=full_name,
            password_hash=hash_password(password),
            user_type=UserType.BRAND_USER.value,
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        print(f"[+] Kullanıcı oluşturuldu: {user.email} ({user.id})")
    else:
        print(f"[=] Kullanıcı bulundu: {user.email} ({user.id})")
        if user.user_type != UserType.BRAND_USER.value:
            print(
                f"[!] UYARI: Kullanıcı tipi '{user.user_type}', 'brand_user' bekleniyor. Değiştirilmiyor."
            )

    # ── 4. Brand membership ────────────────────────────────────────────────────
    from datetime import UTC, datetime

    result = await db.execute(
        select(BrandMember).where(
            BrandMember.brand_id == brand.id,
            BrandMember.user_id == user.id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        membership = BrandMember(
            brand_id=brand.id,
            user_id=user.id,
            role=BrandMemberRole.BRAND_MANAGER.value,
            status=BrandMemberStatus.ACTIVE.value,
            joined_at=datetime.now(UTC),
        )
        db.add(membership)
        await db.flush()
        print(
            f"[+] Brand membership oluşturuldu: {user.email} -> {brand.name} "
            f"(rol: {membership.role})"
        )
    else:
        print(
            f"[=] Brand membership zaten var: {user.email} -> {brand.name} "
            f"(rol: {membership.role})"
        )

    print()
    print("-" * 55)
    print(f"  Ajans   : {agency.name}")
    print(f"  Marka   : {brand.name}")
    print(f"  E-posta : {user.email}")
    print(f"  Tip     : {user.user_type}")
    print(f"  Rol     : {membership.role}")
    print("-" * 55)
    print("Tamamlandi. Kullanici /brand/login ile giris yapabilir.")


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Flobrief brand kullanıcısı oluştur")
    p.add_argument("--agency-name", required=True)
    p.add_argument("--brand-name", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--full-name", required=True)
    p.add_argument("--password", required=True)
    return p.parse_args()


if __name__ == "__main__":
    args = _parse()

    # Basic password strength check (mirrors backend validator)
    pw = args.password
    errors: list[str] = []
    if len(pw) < 10:
        errors.append("En az 10 karakter olmalıdır")
    if not re.search(r"[A-Z]", pw):
        errors.append("En az bir büyük harf içermelidir")
    if not re.search(r"[a-z]", pw):
        errors.append("En az bir küçük harf içermelidir")
    if not re.search(r"\d", pw):
        errors.append("En az bir rakam içermelidir")
    if not re.search(r"[^a-zA-Z0-9]", pw):
        errors.append("En az bir özel karakter içermelidir")
    if errors:
        print("Şifre politikası hatası:")
        for e in errors:
            print(f"  • {e}")
        sys.exit(1)

    print(f"Veritabanı: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else '...'}")
    print()
    asyncio.run(
        run(
            agency_name=args.agency_name,
            brand_name=args.brand_name,
            email=args.email,
            full_name=args.full_name,
            password=args.password,
        )
    )

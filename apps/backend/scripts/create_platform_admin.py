#!/usr/bin/env python3
"""Flobrief Platform Admin Bootstrap CLI.

Creates a platform_admin user directly in the database.
No registration or invitation flow — this is the only way to create platform admins.

Usage (run from apps/backend/):
    python scripts/create_platform_admin.py --email admin@example.com --full-name "Admin User"

SECURITY WARNING:
  - This script grants full platform-level access.
  - Production use: run via deploy pipeline only, not from a developer terminal.
  - MFA will be enforced in Part 13 before this account can be used in production.
"""
import argparse
import asyncio
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.enums import UserType  # noqa: E402
from app.models.user import User  # noqa: E402


async def _create(email: str, full_name: str, password: str) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == email.lower())
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            if existing.user_type == UserType.PLATFORM_ADMIN.value:
                print(f"[WARN] platform_admin already exists for {email}. No changes made.")
            else:
                print(f"[ERROR] A non-admin account with {email} already exists. Aborting.")
                sys.exit(1)
            return

        user = User(
            email=email.lower(),
            password_hash=hash_password(password),
            full_name=full_name,
            user_type=UserType.PLATFORM_ADMIN.value,
            is_active=True,
            is_verified=True,
            mfa_enabled=False,
        )
        session.add(user)
        await session.commit()

    print(f"[OK] platform_admin created: {email}")
    print("[WARN] MFA is currently disabled. Enable MFA (Part 13) before production use.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a Flobrief platform_admin user.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--full-name", required=True, dest="full_name", help="Admin full name")
    args = parser.parse_args()

    print("=" * 60)
    print("  FLOBRIEF PLATFORM ADMIN BOOTSTRAP")
    print("=" * 60)
    print("[SECURITY] Platform admins have full system access.")
    print("[SECURITY] Production: run via deploy pipeline only.")
    print()

    password = getpass.getpass("Password (min 12 chars): ")
    if len(password) < 12:
        print("[ERROR] Password must be at least 12 characters.")
        sys.exit(1)

    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("[ERROR] Passwords do not match.")
        sys.exit(1)

    asyncio.run(_create(args.email, args.full_name, password))


if __name__ == "__main__":
    main()

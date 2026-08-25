#!/usr/bin/env python3
"""PostPiloter Platform Admin Password Reset CLI.

Resets the password of an existing platform_admin account directly in the database.
Minimum 5 characters required. No API validation rules apply here.

Usage (run from apps/backend/):
    python scripts/reset_admin_password.py --email admin@example.com
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


async def _reset(email: str, new_password: str) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == email.lower()))
        user = result.scalar_one_or_none()

        if user is None:
            print(f"[ERROR] No user found with email '{email}'.")
            sys.exit(1)

        if user.user_type != UserType.PLATFORM_ADMIN.value:
            print(
                f"[ERROR] '{email}' is not a platform_admin "
                f"(user_type={user.user_type}). Aborting."
            )
            sys.exit(1)

        user.password_hash = hash_password(new_password)
        session.add(user)
        await session.commit()

    print(f"[OK] Password updated for platform_admin: {email}")
    print("     You can now log in at /platform/login with the new password.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset a platform_admin password.")
    parser.add_argument("--email", required=True, help="Admin email address")
    args = parser.parse_args()

    print(f"Resetting password for: {args.email}")
    new_password = getpass.getpass("New password (min 5 chars): ")
    confirm = getpass.getpass("Confirm new password: ")

    if new_password != confirm:
        print("[ERROR] Passwords do not match.")
        sys.exit(1)

    if len(new_password) < 5:
        print("[ERROR] Password must be at least 5 characters.")
        sys.exit(1)

    asyncio.run(_reset(args.email, new_password))


if __name__ == "__main__":
    main()

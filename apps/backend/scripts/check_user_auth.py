#!/usr/bin/env python3
"""Flobrief User Auth Debug Script.

Checks whether a user exists and shows auth-relevant fields.
NEVER prints password hash or sensitive secrets.

Usage (run from apps/backend/):
    python scripts/check_user_auth.py --email user@example.com
    python scripts/check_user_auth.py --email user@example.com --verify-password
"""

import argparse
import asyncio
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.security import verify_password  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402


async def check(email: str, do_verify: bool = False) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == email.lower()))
        user = result.scalar_one_or_none()

    if user is None:
        print(f"[NOT FOUND] No user with email '{email}'.")
        sys.exit(1)

    print("=" * 50)
    print("  USER RECORD")
    print("=" * 50)
    print(f"  id          : {user.id}")
    print(f"  email       : {user.email}")
    print(f"  full_name   : {user.full_name}")
    print(f"  user_type   : {user.user_type}")
    print(f"  is_active   : {user.is_active}")
    print(f"  is_verified : {user.is_verified}")
    print(f"  mfa_enabled : {user.mfa_enabled}")
    print(f"  is_deleted  : {user.is_deleted}  (deleted_at={user.deleted_at})")
    print(f"  last_login  : {user.last_login_at}")
    print(f"  created_at  : {user.created_at}")
    print(f"  hash_set    : {'YES' if user.password_hash else 'NO'}")
    print("=" * 50)

    issues = []
    if not user.is_active:
        issues.append("Account is INACTIVE — login will be rejected")
    if not user.is_verified:
        issues.append("Account is UNVERIFIED — login will be rejected")
    if user.is_deleted:
        issues.append("Account is SOFT-DELETED — login will be rejected")
    if not user.password_hash:
        issues.append("password_hash is EMPTY — password can never match")

    if issues:
        print("[ISSUES]")
        for i in issues:
            print(f"  ✗ {i}")
    else:
        print("[OK] Account is in a valid state for login.")

    if user.user_type == "platform_admin":
        print("[INFO] This is a platform_admin — must use /platform/login, not /auth/login.")
    elif user.user_type == "agency_user":
        print("[INFO] This is an agency_user — must use /auth/login.")

    if do_verify:
        print()
        print("── Password Verification ──────────────────────────")
        if not user.password_hash:
            print("[SKIP] No password hash stored — cannot verify.")
            return
        try:
            candidate = getpass.getpass("Enter password to verify (input hidden): ")
        except (EOFError, KeyboardInterrupt):
            print("\n[ABORTED]")
            return
        result_ok = verify_password(candidate, user.password_hash)
        if result_ok:
            print("[✓] Password MATCHES the stored hash — login should succeed.")
        else:
            print("[✗] Password does NOT match the stored hash — login will fail with 401.")
            print("    Run: python scripts/reset_admin_password.py --email", email)
        print("=" * 50)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Flobrief user auth state.")
    parser.add_argument("--email", required=True, help="User email to check")
    parser.add_argument(
        "--verify-password",
        action="store_true",
        dest="verify_password",
        help="Interactively verify a password against the stored hash (input hidden)",
    )
    args = parser.parse_args()
    asyncio.run(check(args.email, do_verify=args.verify_password))


if __name__ == "__main__":
    main()

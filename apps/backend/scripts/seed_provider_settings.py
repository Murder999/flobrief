"""
Seed script: upserts Resend and Twilio provider credentials into platform_provider_settings.
Run from apps/backend directory:
  python scripts/seed_provider_settings.py
"""

from __future__ import annotations

import asyncio
import os
import sys

# Allow importing app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("APP_ENV", "development")

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.platform_provider_settings import PlatformProviderSetting
from app.services.secret_encryption import secret_encryption


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


RESEND_API_KEY = _required_env("RESEND_API_KEY")
RESEND_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "PostPiloter")
RESEND_FROM_EMAIL = os.getenv("EMAIL_FROM", "onboarding@resend.dev")
RESEND_REPLY_TO = os.getenv("EMAIL_REPLY_TO", "")

TWILIO_ACCOUNT_SID = _required_env("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = _required_env("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = _required_env("TWILIO_WHATSAPP_FROM")


def _mask_api_key(key: str) -> str:
    if len(key) <= 4:
        return "re_••••"
    return "re_••••••••" + key[-4:]


def _mask_sid(sid: str) -> str:
    if len(sid) < 8:
        return sid
    return sid[:4] + "••••" + sid[-4:]


def _mask_from(number: str) -> str:
    if len(number) <= 4:
        return number
    return number[:-4] + "****"


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        # ── Resend email provider ─────────────────────────────────────────────
        result = await db.execute(
            select(PlatformProviderSetting).where(
                PlatformProviderSetting.provider == "email_resend"
            )
        )
        row = result.scalar_one_or_none()

        enc_key = secret_encryption.encrypt(RESEND_API_KEY)
        masked_key = _mask_api_key(RESEND_API_KEY)
        now = datetime.now(UTC)

        if row is None:
            row = PlatformProviderSetting(
                provider="email_resend",
                provider_type="resend",
                is_enabled=True,
                encrypted_api_key=enc_key,
                email_api_key_masked=masked_key,
                email_from_name=RESEND_FROM_NAME,
                email_from_email=RESEND_FROM_EMAIL,
                email_reply_to=RESEND_REPLY_TO or None,
                configured_at=now,
            )
            db.add(row)
            print(f"  [+] email_resend row created — key masked: {masked_key}")
        else:
            row.is_enabled = True
            row.encrypted_api_key = enc_key
            row.email_api_key_masked = masked_key
            row.email_from_name = RESEND_FROM_NAME
            row.email_from_email = RESEND_FROM_EMAIL
            row.email_reply_to = RESEND_REPLY_TO or None
            row.configured_at = now
            print(f"  [~] email_resend row updated — key masked: {masked_key}")

        # ── Twilio WhatsApp provider ──────────────────────────────────────────
        result2 = await db.execute(
            select(PlatformProviderSetting).where(
                PlatformProviderSetting.provider == "whatsapp_twilio"
            )
        )
        row2 = result2.scalar_one_or_none()

        enc_sid = secret_encryption.encrypt(TWILIO_ACCOUNT_SID)
        enc_token = secret_encryption.encrypt(TWILIO_AUTH_TOKEN)
        enc_from = secret_encryption.encrypt(TWILIO_WHATSAPP_FROM)
        sid_masked = _mask_sid(TWILIO_ACCOUNT_SID)
        from_masked = _mask_from(TWILIO_WHATSAPP_FROM)

        if row2 is None:
            row2 = PlatformProviderSetting(
                provider="whatsapp_twilio",
                provider_type="twilio_sandbox",
                is_enabled=True,
                encrypted_account_sid=enc_sid,
                encrypted_auth_token=enc_token,
                encrypted_whatsapp_from=enc_from,
                account_sid_last4=TWILIO_ACCOUNT_SID[-4:],
                whatsapp_from_masked=from_masked,
                configured_at=now,
            )
            db.add(row2)
            print(f"  [+] whatsapp_twilio row created — SID masked: {sid_masked}")
        else:
            row2.is_enabled = True
            row2.provider_type = "twilio_sandbox"
            row2.encrypted_account_sid = enc_sid
            row2.encrypted_auth_token = enc_token
            row2.encrypted_whatsapp_from = enc_from
            row2.account_sid_last4 = TWILIO_ACCOUNT_SID[-4:]
            row2.whatsapp_from_masked = from_masked
            row2.configured_at = now
            print(f"  [~] whatsapp_twilio row updated — SID masked: {sid_masked}")

        await db.commit()
        print("\nDone. Both provider rows are now active in the DB.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

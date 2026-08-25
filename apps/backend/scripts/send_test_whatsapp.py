"""Dev script: send a test WhatsApp message via the configured Twilio provider.

Usage:
  python scripts/send_test_whatsapp.py --to "+905xxxxxxxxx" --message "Test mesajı"
  python scripts/send_test_whatsapp.py --to "+905xxxxxxxxx"  # uses default message

Runs outside FastAPI — reads settings from .env, loads DB config, fetches provider
settings, decrypts secrets, sends the message.

SECRET SAFETY:
  - Never prints decrypted secrets.
  - Masks phone numbers in output.
  - Does NOT run in production (APP_ENV=production is blocked).
"""

from __future__ import annotations

import argparse
import asyncio
import sys

sys.path.insert(0, ".")


async def _main(to_phone: str, message: str) -> None:
    import os

    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

    from app.core.config import settings

    if settings.is_production:
        print(
            "ERROR: This script must not run in production (APP_ENV=production).", file=sys.stderr
        )
        sys.exit(1)

    if not settings.FLOBRIEF_SECRET_ENCRYPTION_KEY:
        print(
            "ERROR: FLOBRIEF_SECRET_ENCRYPTION_KEY is not set. " "Cannot decrypt provider secrets.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not settings.WHATSAPP_NOTIFICATIONS_ENABLED:
        print(
            "WARNING: WHATSAPP_NOTIFICATIONS_ENABLED=false. "
            "Provider will return 'not_configured'. "
            "Set WHATSAPP_NOTIFICATIONS_ENABLED=true to test real sends.",
        )

    from app.db.session import AsyncSessionLocal
    from app.services.whatsapp_provider import DisabledWhatsAppProvider, WhatsAppProviderFactory

    def _mask(phone: str) -> str:
        clean = phone.replace("whatsapp:", "")
        if len(clean) <= 6:
            return "***"
        return clean[:4] + "***" + clean[-2:]

    async with AsyncSessionLocal() as session:
        provider = await WhatsAppProviderFactory.get_provider(session)

    print(f"Provider: {provider.get_provider_name()}")
    print(f"To: {_mask(to_phone)}")
    print("Sending...")

    if isinstance(provider, DisabledWhatsAppProvider):
        print("Provider is disabled/not configured. Message will NOT be sent.")
        result = provider.send_message(to_phone, message)
    else:
        result = provider.send_message(to_phone, message)

    print("\nResult:")
    print(f"  Status:      {result.status}")
    print(f"  Provider:    {result.provider}")
    print(f"  Message SID: {result.provider_message_id or '—'}")
    if result.error_message:
        print(f"  Error:       {result.error_message}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a test WhatsApp message via Twilio.")
    parser.add_argument("--to", required=True, help="Recipient phone in E.164 format (+905...)")
    parser.add_argument(
        "--message",
        default="PostPiloter test WhatsApp bildirimi. Provider yapılandırması başarılı.",
        help="Message body",
    )
    args = parser.parse_args()
    asyncio.run(_main(args.to, args.message))


if __name__ == "__main__":
    main()

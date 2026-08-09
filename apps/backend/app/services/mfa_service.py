"""TOTP-based MFA service. No external MFA libraries — TOTP implemented per RFC 6238."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import UTC, datetime
from urllib.parse import quote

import bcrypt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.models.user_mfa_recovery_code import UserMfaRecoveryCode

_BCRYPT_ROUNDS = 12
_RECOVERY_CODE_COUNT = 8


def _hash_recovery_code(code: str) -> str:
    return bcrypt.hashpw(
        code.encode("utf-8"),
        bcrypt.gensalt(rounds=_BCRYPT_ROUNDS),
    ).decode("ascii")


def _verify_recovery_code(code: str, code_hash: str) -> bool:
    try:
        return bcrypt.checkpw(code.encode("utf-8"), code_hash.encode("ascii"))
    except (ValueError, TypeError, UnicodeError):
        return False


# ── TOTP core (RFC 6238) ──────────────────────────────────────────────────────


def _totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode()


def _hotp(secret_bytes: bytes, counter: int) -> int:
    msg = struct.pack(">Q", counter)
    mac = hmac.new(secret_bytes, msg, hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    code = struct.unpack(">I", mac[offset : offset + 4])[0] & 0x7FFFFFFF
    return code % 1_000_000


def _verify_totp(secret_b32: str, code: str, window: int = 1) -> bool:
    if not code.isdigit() or len(code) != 6:
        return False
    try:
        secret_bytes = base64.b32decode(secret_b32.upper())
    except Exception:
        return False
    counter = int(time.time()) // 30
    code_int = int(code)
    return any(
        _hotp(secret_bytes, counter + delta) == code_int for delta in range(-window, window + 1)
    )


def build_otpauth_url(secret: str, email: str) -> str:
    issuer = "Flobrief"
    label = f"{quote(issuer)}:{quote(email)}"
    return (
        f"otpauth://totp/{label}"
        f"?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"
    )


# ── Encryption helpers ────────────────────────────────────────────────────────


def _fernet() -> object:
    from cryptography.fernet import Fernet

    key = settings.TOTP_ENCRYPTION_KEY
    if not key:
        raw = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        key = base64.urlsafe_b64encode(raw).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_totp_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()  # type: ignore[union-attr]


def decrypt_totp_secret(encrypted: str) -> str:
    return _fernet().decrypt(encrypted.encode()).decode()  # type: ignore[union-attr]


# ── Recovery codes ────────────────────────────────────────────────────────────


def _gen_recovery_codes() -> list[str]:
    codes = []
    for _ in range(_RECOVERY_CODE_COUNT):
        p1 = secrets.token_hex(3).upper()
        p2 = secrets.token_hex(3).upper()
        codes.append(f"{p1}-{p2}")
    return codes


# ── Service ───────────────────────────────────────────────────────────────────


class MfaService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def begin_setup(self, user: User) -> tuple[str, str]:
        """Generate and store (encrypted) TOTP secret without enabling MFA yet.

        Returns (secret_b32, otpauth_url). Call confirm_setup to activate.
        """
        if user.mfa_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="MFA already enabled"
            )
        secret = _totp_secret()
        user.mfa_secret_encrypted = encrypt_totp_secret(secret)
        self.db.add(user)
        await self.db.flush()
        return secret, build_otpauth_url(secret, user.email)

    async def confirm_setup(self, user: User, code: str) -> list[str]:
        """Verify TOTP code, enable MFA, generate recovery codes (returned once)."""
        if user.mfa_enabled:
            raise HTTPException(status_code=400, detail="MFA already enabled")
        if not user.mfa_secret_encrypted:
            raise HTTPException(status_code=400, detail="Call /mfa/setup first")

        secret = decrypt_totp_secret(user.mfa_secret_encrypted)
        if not _verify_totp(secret, code):
            raise HTTPException(status_code=400, detail="Invalid TOTP code")

        user.mfa_enabled = True
        self.db.add(user)

        await self._delete_recovery_codes(user.id)

        raw_codes = _gen_recovery_codes()
        for raw in raw_codes:
            self.db.add(UserMfaRecoveryCode(user_id=user.id, code_hash=_hash_recovery_code(raw)))

        await self.db.flush()
        return raw_codes

    async def disable(self, user: User, code: str) -> None:
        """Disable MFA after verifying current TOTP code."""
        if not user.mfa_enabled or not user.mfa_secret_encrypted:
            raise HTTPException(status_code=400, detail="MFA not enabled")

        secret = decrypt_totp_secret(user.mfa_secret_encrypted)
        if not _verify_totp(secret, code):
            raise HTTPException(status_code=400, detail="Invalid TOTP code")

        user.mfa_enabled = False
        user.mfa_secret_encrypted = None
        self.db.add(user)
        await self._delete_recovery_codes(user.id)
        await self.db.flush()

    async def verify_code(self, user: User, code: str) -> bool:
        """Return True if the TOTP code is valid for this user."""
        if not user.mfa_enabled or not user.mfa_secret_encrypted:
            return False
        secret = decrypt_totp_secret(user.mfa_secret_encrypted)
        return _verify_totp(secret, code)

    async def use_recovery_code(self, user: User, raw_code: str) -> bool:
        """Consume a recovery code. Returns True if valid; marks it used."""
        result = await self.db.execute(
            select(UserMfaRecoveryCode).where(
                UserMfaRecoveryCode.user_id == user.id,
                UserMfaRecoveryCode.used_at.is_(None),
            )
        )
        for record in result.scalars().all():
            if _verify_recovery_code(raw_code, record.code_hash):
                record.used_at = datetime.now(UTC)
                self.db.add(record)
                await self.db.flush()
                return True
        return False

    async def regenerate_recovery_codes(self, user: User, code: str) -> list[str]:
        """Re-generate all recovery codes after verifying current TOTP."""
        if not user.mfa_enabled or not user.mfa_secret_encrypted:
            raise HTTPException(status_code=400, detail="MFA not enabled")

        secret = decrypt_totp_secret(user.mfa_secret_encrypted)
        if not _verify_totp(secret, code):
            raise HTTPException(status_code=400, detail="Invalid TOTP code")

        await self._delete_recovery_codes(user.id)

        raw_codes = _gen_recovery_codes()
        for raw in raw_codes:
            self.db.add(UserMfaRecoveryCode(user_id=user.id, code_hash=_hash_recovery_code(raw)))

        await self.db.flush()
        return raw_codes

    async def _delete_recovery_codes(self, user_id: object) -> None:
        result = await self.db.execute(
            select(UserMfaRecoveryCode).where(UserMfaRecoveryCode.user_id == user_id)
        )
        for rec in result.scalars().all():
            await self.db.delete(rec)
        await self.db.flush()

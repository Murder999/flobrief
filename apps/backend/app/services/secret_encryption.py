"""Field-level secret encryption for platform provider credentials.

Uses Fernet (AES-128-CBC + HMAC-SHA256) authenticated encryption.
Master key must be set via FLOBRIEF_SECRET_ENCRYPTION_KEY env var.
Key must NEVER appear in API responses, logs, or frontend bundles.
"""

from __future__ import annotations

from app.core.config import settings


class SecretEncryptionError(Exception):
    """Raised when encryption key is missing or decryption fails."""


def _get_fernet() -> object:
    from cryptography.fernet import Fernet

    key = settings.FLOBRIEF_SECRET_ENCRYPTION_KEY
    if not key:
        raise SecretEncryptionError(
            "FLOBRIEF_SECRET_ENCRYPTION_KEY ortam değişkeni ayarlanmamış. "
            "Şifreli secret kaydedilemiyor. "
            'Üret: python -c "from cryptography.fernet import Fernet;'
            ' print(Fernet.generate_key().decode())"'
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


class SecretEncryptionService:
    """Encrypt and decrypt sensitive provider credentials before DB storage.

    Never call decrypt() outside of provider runtime code that needs the raw value.
    API responses must NEVER contain decrypted values.
    """

    @staticmethod
    def is_configured() -> bool:
        return bool(settings.FLOBRIEF_SECRET_ENCRYPTION_KEY)

    @staticmethod
    def encrypt(plain: str) -> str:
        """Encrypt a plaintext secret. Returns Fernet token (URL-safe base64)."""
        if not plain:
            raise SecretEncryptionError("Cannot encrypt empty string")
        fernet = _get_fernet()
        return fernet.encrypt(plain.encode()).decode()  # type: ignore[union-attr]

    @staticmethod
    def decrypt(encrypted: str) -> str:
        """Decrypt a Fernet-encrypted secret. Only call at provider runtime."""
        if not encrypted:
            raise SecretEncryptionError("Cannot decrypt empty string")
        fernet = _get_fernet()
        try:
            return fernet.decrypt(encrypted.encode()).decode()  # type: ignore[union-attr]
        except Exception as exc:
            raise SecretEncryptionError("Secret decryption failed") from exc


secret_encryption = SecretEncryptionService()

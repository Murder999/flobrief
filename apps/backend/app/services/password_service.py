import re

from app.core.security import hash_password, verify_password

_COMMON_PASSWORDS: frozenset[str] = frozenset(
    {
        "password123!",
        "Password1!",
        "Qwerty1234!",
        "12345678!a",
        "Admin1234!",
        "Welcome1!",
        "Flobrief1!",
        "PostPiloter1!",
        "Passw0rd!",
        "Test1234!",
        "Summer2024!",
    }
)


def validate_password_policy(password: str) -> list[str]:
    """Returns list of policy violation messages. Empty = valid."""
    errors: list[str] = []
    if len(password) < 10:
        errors.append("En az 10 karakter olmalıdır")
    if not re.search(r"[A-Z]", password):
        errors.append("En az bir büyük harf içermelidir")
    if not re.search(r"[a-z]", password):
        errors.append("En az bir küçük harf içermelidir")
    if not re.search(r"\d", password):
        errors.append("En az bir rakam içermelidir")
    if not re.search(r"[^a-zA-Z0-9]", password):
        errors.append("En az bir özel karakter içermelidir")
    if password in _COMMON_PASSWORDS:
        errors.append("Bu şifre çok yaygın")
    return errors


def is_password_valid(password: str) -> bool:
    return len(validate_password_policy(password)) == 0


def hash_new_password(password: str) -> str:
    return hash_password(password)


def check_password(plain: str, hashed: str) -> bool:
    return verify_password(plain, hashed)

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.security import hash_password, verify_password
from app.schemas.auth import ChangePasswordRequest
from app.services.auth_service import AuthService
from app.services.token_service import TOKEN_TYPE_REFRESH


def _service() -> tuple[AuthService, MagicMock]:
    db = MagicMock()
    db.commit = AsyncMock()
    service = AuthService(db)
    service.token_repo = MagicMock()
    service.token_repo.revoke_all_for_user = AsyncMock()
    return service, db


def _user(password: str = "Current@2024#") -> MagicMock:
    user = MagicMock()
    user.id = uuid4()
    user.password_hash = hash_password(password)
    return user


class TestChangePasswordService:
    async def test_changes_hash_and_revokes_refresh_tokens(self) -> None:
        service, db = _service()
        user = _user()

        await service.change_password(
            user,
            ChangePasswordRequest(
                current_password="Current@2024#",
                new_password="MyChosen@2026#",
            ),
        )

        assert verify_password("MyChosen@2026#", user.password_hash)
        service.token_repo.revoke_all_for_user.assert_awaited_once_with(
            user.id,
            TOKEN_TYPE_REFRESH,
        )
        db.add.assert_called_once_with(user)
        db.commit.assert_awaited_once()

    async def test_rejects_wrong_current_password(self) -> None:
        service, db = _service()
        user = _user()

        with pytest.raises(HTTPException) as error:
            await service.change_password(
                user,
                ChangePasswordRequest(
                    current_password="WrongCurrent@2024#",
                    new_password="MyChosen@2026#",
                ),
            )

        assert error.value.status_code == 400
        assert "Mevcut şifre" in error.value.detail
        db.commit.assert_not_awaited()

    async def test_rejects_reusing_current_password(self) -> None:
        service, db = _service()
        user = _user()

        with pytest.raises(HTTPException) as error:
            await service.change_password(
                user,
                ChangePasswordRequest(
                    current_password="Current@2024#",
                    new_password="Current@2024#",
                ),
            )

        assert error.value.status_code == 400
        assert "aynı olamaz" in error.value.detail
        db.commit.assert_not_awaited()

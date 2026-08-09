from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_token import UserToken


class UserTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        token_hash: str,
        token_family: uuid.UUID,
        token_type: str,
        expires_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> UserToken:
        token = UserToken(
            user_id=user_id,
            token_hash=token_hash,
            token_family=token_family,
            token_type=token_type,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.session.add(token)
        await self.session.flush()
        await self.session.refresh(token)
        return token

    async def get_by_hash(self, token_hash: str) -> UserToken | None:
        result = await self.session.execute(
            select(UserToken).where(UserToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke(self, token: UserToken) -> None:
        token.revoked_at = datetime.now(UTC)
        self.session.add(token)
        await self.session.flush()

    async def revoke_family(self, token_family: uuid.UUID) -> None:
        stmt = (
            update(UserToken)
            .where(UserToken.token_family == token_family, UserToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def revoke_all_for_user(self, user_id: uuid.UUID, token_type: str | None = None) -> None:
        conditions = [UserToken.user_id == user_id, UserToken.revoked_at.is_(None)]
        if token_type:
            conditions.append(UserToken.token_type == token_type)
        stmt = update(UserToken).where(*conditions).values(revoked_at=datetime.now(UTC))
        await self.session.execute(stmt)
        await self.session.flush()

    def is_valid(self, token: UserToken) -> bool:
        now = datetime.now(UTC)
        return token.revoked_at is None and token.expires_at.replace(tzinfo=UTC) > now

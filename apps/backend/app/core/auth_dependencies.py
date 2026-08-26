from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.impersonation_sessions import is_impersonation_session_active
from app.core.rbac import Permission, get_permissions_for_agency_role
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.enums import AgencyMemberStatus, AgencyStatus, UserType
from app.models.user import User
from app.services.demo_access import (
    enforce_demo_workspace_request,
    ensure_demo_user_access,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kimlik doğrulama gerekli",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz veya süresi dolmuş token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from err

    if payload.get("is_impersonation"):
        impersonator_id = payload.get("impersonator_id")
        jti = payload.get("jti")
        if (
            not impersonator_id
            or not jti
            or not await is_impersonation_session_active(str(impersonator_id), jti)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Impersonation oturumu artık aktif değil",
                headers={"WWW-Authenticate": "Bearer"},
            )

    user_id_raw = payload.get("sub")
    try:
        user_id = UUID(str(user_id_raw))
    except (ValueError, TypeError) as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz token",
        ) from err

    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı bulunamadı veya devre dışı",
        )

    await ensure_demo_user_access(db, user.id, payload.get("demo_session_id"))
    return user


async def require_verified(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="E-posta adresinizi doğrulamanız gerekmektedir",
        )
    return current_user


@dataclass
class WorkspaceContext:
    user: User
    agency: Agency
    member: AgencyMember
    permissions: frozenset[Permission]

    def has_permission(self, perm: Permission) -> bool:
        return perm in self.permissions


async def get_workspace_context(
    request: Request,
    x_agency_id: str | None = Header(default=None, alias="X-Agency-ID"),
    current_user: User = Depends(require_verified),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceContext:
    """Resolves agency workspace from X-Agency-ID header. Tenant-isolation enforced."""
    if current_user.user_type == UserType.PLATFORM_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="platform_admin tenant endpoint'lerine erişemez",
        )

    if not x_agency_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Agency-ID başlığı gerekli",
        )

    try:
        agency_id = UUID(x_agency_id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Geçersiz X-Agency-ID formatı",
        ) from err

    agency_result = await db.execute(
        select(Agency).where(
            Agency.id == agency_id,
            Agency.status == AgencyStatus.ACTIVE.value,
            Agency.deleted_at.is_(None),
        )
    )
    agency = agency_result.scalar_one_or_none()
    if agency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency bulunamadı")
    enforce_demo_workspace_request(agency, request)

    member_result = await db.execute(
        select(AgencyMember).where(
            AgencyMember.agency_id == agency_id,
            AgencyMember.user_id == current_user.id,
            AgencyMember.status == AgencyMemberStatus.ACTIVE.value,
            AgencyMember.deleted_at.is_(None),
        )
    )
    member = member_result.scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu agency için aktif üyeliğiniz bulunmuyor",
        )

    permissions = get_permissions_for_agency_role(member.role)
    return WorkspaceContext(
        user=current_user,
        agency=agency,
        member=member,
        permissions=permissions,
    )


def require_permission(perm: Permission) -> Callable[..., WorkspaceContext]:
    """Factory: returns a dependency that enforces a specific permission."""

    async def _dep(
        workspace: WorkspaceContext = Depends(get_workspace_context),
    ) -> WorkspaceContext:
        if not workspace.has_permission(perm):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Gerekli yetki: {perm.value}",
            )
        return workspace

    return _dep

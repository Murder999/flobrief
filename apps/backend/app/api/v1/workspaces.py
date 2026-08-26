from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import require_verified
from app.core.rbac import get_permissions_for_user_type
from app.db.session import get_db
from app.models.enums import AgencyMemberStatus
from app.models.user import User
from app.schemas.permission import PermissionResponse
from app.schemas.workspace import WorkspaceListResponse
from app.services.workspace_service import WorkspaceService

workspace_router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@workspace_router.get("", response_model=WorkspaceListResponse)
async def list_workspaces(
    current_user: User = Depends(require_verified),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceListResponse:
    """List all agencies and brands the current user is a member of."""
    svc = WorkspaceService(db)
    return await svc.list_workspaces(current_user)


@workspace_router.get("/permissions", response_model=PermissionResponse)
async def my_permissions(
    x_agency_id: str | None = Header(default=None, alias="X-Agency-ID"),
    current_user: User = Depends(require_verified),
    db: AsyncSession = Depends(get_db),
) -> PermissionResponse:
    """Return the current user's permissions (optionally scoped to an agency)."""
    from uuid import UUID

    from sqlalchemy import select

    from app.models.agency_member import AgencyMember

    role: str | None = None
    agency_id_str: str | None = None

    if x_agency_id and not current_user.is_platform_admin:
        try:
            agency_uuid = UUID(x_agency_id)
        except ValueError:
            agency_uuid = None

        if agency_uuid:
            result = await db.execute(
                select(AgencyMember).where(
                    AgencyMember.agency_id == agency_uuid,
                    AgencyMember.user_id == current_user.id,
                    AgencyMember.status == AgencyMemberStatus.ACTIVE.value,
                    AgencyMember.deleted_at.is_(None),
                )
            )
            member = result.scalar_one_or_none()
            if member:
                role = member.role
                agency_id_str = str(agency_uuid)

    perms = get_permissions_for_user_type(current_user.user_type, role)
    return PermissionResponse(
        user_type=current_user.user_type,
        agency_id=agency_id_str,
        role=role,
        permissions=sorted(p.value for p in perms),
    )

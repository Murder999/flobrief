from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.agency import AgencyRepository
from app.repositories.agency_member import AgencyMemberRepository
from app.repositories.brand import BrandRepository
from app.repositories.brand_member import BrandMemberRepository
from app.schemas.workspace import WorkspaceAgency, WorkspaceBrand, WorkspaceListResponse


class WorkspaceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.agency_repo = AgencyRepository(db)
        self.agency_member_repo = AgencyMemberRepository(db)
        self.brand_repo = BrandRepository(db)
        self.brand_member_repo = BrandMemberRepository(db)

    async def list_workspaces(self, user: User) -> WorkspaceListResponse:
        """Returns all agencies and brands the user is a member of."""
        agencies = await self.agency_repo.list_for_user(user.id)
        brands = await self.brand_repo.list_for_user(user.id)

        agency_items: list[WorkspaceAgency] = []
        for agency in agencies:
            member = await self.agency_member_repo.get_membership(agency.id, user.id)
            if member:
                agency_items.append(
                    WorkspaceAgency(
                        id=agency.id,
                        name=agency.name,
                        slug=agency.slug,
                        status=agency.status,
                        logo_url=agency.logo_url,
                        member_role=member.role,
                        member_status=member.status,
                    )
                )

        brand_items: list[WorkspaceBrand] = []
        for brand in brands:
            member = await self.brand_member_repo.get_membership(brand.id, user.id)
            if member:
                brand_items.append(
                    WorkspaceBrand(
                        id=brand.id,
                        agency_id=brand.agency_id,
                        name=brand.name,
                        slug=brand.slug,
                        status=brand.status,
                        member_role=member.role,
                        member_status=member.status,
                    )
                )

        return WorkspaceListResponse(agencies=agency_items, brands=brand_items)

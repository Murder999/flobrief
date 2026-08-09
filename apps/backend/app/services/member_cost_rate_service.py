"""MemberCostRateService: CRUD for internal hourly cost rates, with
one-open-ended-rate-per-(user|role) enforcement (plan §3/§7) and
service-layer visibility gating as defense-in-depth on top of the
`COST_RATE_VIEW`/`COST_RATE_MANAGE` RBAC permission check already done at
the API layer (belt and suspenders per plan §12 — cost rates must never
leak to Designer/Developer/Social Media Manager/Brand Manager/brand-portal
users, and per plan §8, not even to Admin by default).

No dedicated "Finance" role exists in `AgencyMemberRole` today — Owner is
the only role plan §8 grants `COST_RATE_VIEW`/`COST_RATE_MANAGE` to.
`_FINANCE_VISIBLE_ROLES` is the single point to widen if a Finance role is
ever introduced."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.models.commercial_terms import MemberCostRate
from app.models.enums import AgencyMemberRole
from app.repositories.member_cost_rate import MemberCostRateRepository
from app.schemas.member_cost_rate import MemberCostRateCreate, MemberCostRateUpdate

_FINANCE_VISIBLE_ROLES = frozenset({AgencyMemberRole.OWNER.value})
_VALID_CURRENCIES = {
    "TRY",
    "USD",
    "EUR",
    "GBP",
    "CHF",
    "JPY",
    "CAD",
    "AUD",
    "SEK",
    "NOK",
    "DKK",
    "PLN",
    "CZK",
    "HUF",
    "RON",
    "BGN",
    "RUB",
    "AED",
    "SAR",
    "QAR",
    "KWD",
    "ILS",
    "CNY",
    "HKD",
    "SGD",
    "INR",
    "ZAR",
    "BRL",
    "MXN",
    "AZN",
}


class MemberCostRateService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = MemberCostRateRepository(db)

    def _require_finance_visibility(self, actor_role: str) -> None:
        if actor_role not in _FINANCE_VISIBLE_ROLES:
            raise PermissionDeniedError("Maliyet oranlarını görüntüleme/yönetme yetkiniz yok")

    def _validate_business_rules(self, currency: str, hourly_cost_cents: int) -> None:
        if currency.upper() not in _VALID_CURRENCIES:
            raise ValidationError(f"Geçersiz para birimi kodu (ISO 4217): {currency}")
        if hourly_cost_cents <= 0:
            raise ValidationError("Saatlik maliyet pozitif olmalı")

    async def create(
        self,
        agency_id: uuid.UUID,
        actor_id: uuid.UUID,
        actor_role: str,
        data: MemberCostRateCreate,
    ) -> tuple[MemberCostRate, uuid.UUID | None]:
        """Returns (new_row, superseded_rate_id) — mirrors
        `CommercialTermsService.create`'s supersede-reporting shape."""
        self._require_finance_visibility(actor_role)
        self._validate_business_rules(data.currency, data.hourly_cost_cents)

        superseded_id: uuid.UUID | None = None
        if data.valid_until is None:
            # Only an open-ended new rate needs to supersede an existing
            # open-ended one — a bounded historical rate never collides
            # with the partial unique index.
            prior = (
                await self._repo.get_open_ended_for_user(agency_id, data.user_id)
                if data.user_id is not None
                else await self._repo.get_open_ended_for_role(agency_id, data.role)
            )
            if prior is not None:
                closed_valid_until = data.valid_from - timedelta(days=1)
                if closed_valid_until < prior.valid_from:
                    closed_valid_until = prior.valid_from
                await self._repo.update(prior, {"active": False, "valid_until": closed_valid_until})
                superseded_id = prior.id

        obj = await self._repo.create(
            {
                "agency_id": agency_id,
                "user_id": data.user_id,
                "role": data.role,
                "currency": data.currency,
                "hourly_cost_cents": data.hourly_cost_cents,
                "valid_from": data.valid_from,
                "valid_until": data.valid_until,
                "active": True,
                "created_by_id": actor_id,
            }
        )
        await self._db.commit()
        await self._db.refresh(obj)
        return obj, superseded_id

    async def update(
        self,
        agency_id: uuid.UUID,
        rate_id: uuid.UUID,
        actor_role: str,
        data: MemberCostRateUpdate,
    ) -> MemberCostRate:
        self._require_finance_visibility(actor_role)
        obj = await self._repo.get_by_id(rate_id, agency_id)
        if obj is None:
            raise NotFoundError("Maliyet oranı", str(rate_id))

        update_data = data.model_dump(exclude_unset=True, exclude_none=True)
        currency = update_data.get("currency", obj.currency)
        hourly_cost_cents = update_data.get("hourly_cost_cents", obj.hourly_cost_cents)
        self._validate_business_rules(currency, hourly_cost_cents)

        new_valid_until = update_data.get("valid_until", obj.valid_until)
        if new_valid_until is not None and new_valid_until < obj.valid_from:
            raise ValidationError("Bitiş tarihi başlangıç tarihinden önce olamaz")

        updated = await self._repo.update(obj, update_data)
        await self._db.commit()
        await self._db.refresh(updated)
        return updated

    async def get(
        self, agency_id: uuid.UUID, rate_id: uuid.UUID, actor_role: str
    ) -> MemberCostRate:
        self._require_finance_visibility(actor_role)
        obj = await self._repo.get_by_id(rate_id, agency_id)
        if obj is None:
            raise NotFoundError("Maliyet oranı", str(rate_id))
        return obj

    async def list_for_user(
        self, agency_id: uuid.UUID, user_id: uuid.UUID, actor_role: str
    ) -> list[MemberCostRate]:
        self._require_finance_visibility(actor_role)
        return await self._repo.list_for_user(agency_id, user_id)

    async def list_for_role(
        self, agency_id: uuid.UUID, role: str, actor_role: str
    ) -> list[MemberCostRate]:
        self._require_finance_visibility(actor_role)
        return await self._repo.list_for_role(agency_id, role)

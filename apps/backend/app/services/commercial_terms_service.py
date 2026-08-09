"""CommercialTermsService: CRUD for the agency<->brand billing arrangement,
with one-active-per-brand enforcement (plan §3/§7). Creating a new term
transactionally closes out the brand's currently-active term (sets
`active=False` and caps its `valid_until` the day before the new term
starts) before inserting the new active row — mirrors
`WorkScheduleService.upsert`'s soft-delete-old+insert-new pattern, except
history is kept (not soft-deleted) since past terms may already be
reflected on issued invoices.

Currency/tax-range/negative-amount validation happens twice by design:
Pydantic schemas reject bad input at the API boundary, and this service
re-validates the same rules server-side as defense-in-depth for any
programmatic caller that bypasses the schema (tests, future internal
callers) — per plan §12."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.commercial_terms import CommercialTerms
from app.models.enums import CommercialTermsBillingModel
from app.repositories.commercial_terms import CommercialTermsRepository
from app.schemas.commercial_terms import CommercialTermsCreate, CommercialTermsUpdate

_VALID_BILLING_MODELS = {m.value for m in CommercialTermsBillingModel}
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
_MONEY_FIELDS = (
    "hourly_rate_cents",
    "fixed_fee_cents",
    "retainer_amount_cents",
    "overage_rate_cents",
    "per_item_rate_cents",
)


class CommercialTermsService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = CommercialTermsRepository(db)

    def _validate_business_rules(
        self,
        billing_model: str,
        currency: str,
        tax_rate_bps: int,
        discount_rate_bps: int | None,
        money_values: dict[str, int | None],
        retainer_included_minutes: int | None,
    ) -> None:
        """Defense-in-depth re-check of everything the Pydantic schema and
        DB CheckConstraints already enforce — never trust that every call
        path went through the schema."""
        if billing_model not in _VALID_BILLING_MODELS:
            raise ValidationError(f"Geçersiz faturalama modeli: {billing_model}")
        if currency.upper() not in _VALID_CURRENCIES:
            raise ValidationError(f"Geçersiz para birimi kodu (ISO 4217): {currency}")
        if not (0 <= tax_rate_bps <= 10000):
            raise ValidationError("Vergi oranı 0-10000 baz puan aralığında olmalı")
        if discount_rate_bps is not None and not (0 <= discount_rate_bps <= 10000):
            raise ValidationError("İndirim oranı 0-10000 baz puan aralığında olmalı")
        for field_name, value in money_values.items():
            if value is not None and value < 0:
                raise ValidationError(f"{field_name} negatif olamaz")
        if retainer_included_minutes is not None and retainer_included_minutes < 0:
            raise ValidationError("Retainer dahil dakika negatif olamaz")

    async def _check_no_overlap(
        self,
        agency_id: uuid.UUID,
        brand_id: uuid.UUID,
        valid_from: date,
        valid_until: date | None,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        overlapping = await self._repo.list_overlapping(
            agency_id, brand_id, valid_from, valid_until, exclude_id=exclude_id
        )
        if overlapping:
            raise ConflictError(
                "Bu marka için belirtilen tarih aralığı mevcut bir ticari koşul kaydıyla çakışıyor"
            )

    async def create(
        self,
        agency_id: uuid.UUID,
        actor_id: uuid.UUID,
        data: CommercialTermsCreate,
    ) -> tuple[CommercialTerms, uuid.UUID | None]:
        """Returns (new_row, superseded_terms_id). `superseded_terms_id` is
        set whenever this create closed out a prior active term for the
        brand — the API layer uses it to also emit a
        `commercial_terms.superseded` activity log entry."""
        self._validate_business_rules(
            data.billing_model,
            data.currency,
            data.tax_rate_bps,
            data.discount_rate_bps,
            {f: getattr(data, f) for f in _MONEY_FIELDS},
            data.retainer_included_minutes,
        )

        prior_active = await self._repo.get_active_for_brand(agency_id, data.brand_id)
        superseded_id: uuid.UUID | None = None
        if prior_active is not None:
            closed_valid_until = data.valid_from - timedelta(days=1)
            if closed_valid_until < prior_active.valid_from:
                closed_valid_until = prior_active.valid_from
            # Never widen a prior row's own already-set end date — closing
            # a term on supersede can only shorten it, matching whichever
            # boundary (the prior row's own `valid_until` or the new row's
            # start) comes first.
            if prior_active.valid_until is not None:
                closed_valid_until = min(closed_valid_until, prior_active.valid_until)
            await self._repo.update(
                prior_active, {"active": False, "valid_until": closed_valid_until}
            )
            superseded_id = prior_active.id

        await self._check_no_overlap(agency_id, data.brand_id, data.valid_from, data.valid_until)

        obj = await self._repo.create(
            {
                "agency_id": agency_id,
                "brand_id": data.brand_id,
                "billing_model": data.billing_model,
                "currency": data.currency,
                "hourly_rate_cents": data.hourly_rate_cents,
                "fixed_fee_cents": data.fixed_fee_cents,
                "retainer_amount_cents": data.retainer_amount_cents,
                "retainer_included_minutes": data.retainer_included_minutes,
                "overage_rate_cents": data.overage_rate_cents,
                "per_item_rate_cents": data.per_item_rate_cents,
                "payment_terms_days": data.payment_terms_days,
                "tax_rate_bps": data.tax_rate_bps,
                "discount_rate_bps": data.discount_rate_bps,
                "billing_contact_name": data.billing_contact_name,
                "billing_contact_email": data.billing_contact_email,
                "billing_address": data.billing_address,
                "tax_office": data.tax_office,
                "tax_number": data.tax_number,
                "valid_from": data.valid_from,
                "valid_until": data.valid_until,
                "active": True,
                "created_by_id": actor_id,
                "updated_by_id": actor_id,
            }
        )
        await self._db.commit()
        await self._db.refresh(obj)
        return obj, superseded_id

    async def update(
        self,
        agency_id: uuid.UUID,
        terms_id: uuid.UUID,
        actor_id: uuid.UUID,
        data: CommercialTermsUpdate,
    ) -> CommercialTerms:
        obj = await self._repo.get_by_id(terms_id, agency_id)
        if obj is None:
            raise NotFoundError("Ticari koşul", str(terms_id))

        update_data = data.model_dump(exclude_unset=True, exclude_none=True)

        billing_model = update_data.get("billing_model", obj.billing_model)
        currency = update_data.get("currency", obj.currency)
        tax_rate_bps = update_data.get("tax_rate_bps", obj.tax_rate_bps)
        discount_rate_bps = update_data.get("discount_rate_bps", obj.discount_rate_bps)
        money_values = {f: update_data.get(f, getattr(obj, f)) for f in _MONEY_FIELDS}
        retainer_included_minutes = update_data.get(
            "retainer_included_minutes", obj.retainer_included_minutes
        )
        self._validate_business_rules(
            billing_model,
            currency,
            tax_rate_bps,
            discount_rate_bps,
            money_values,
            retainer_included_minutes,
        )

        new_valid_until = update_data.get("valid_until", obj.valid_until)
        if new_valid_until is not None and new_valid_until < obj.valid_from:
            raise ValidationError("Bitiş tarihi başlangıç tarihinden önce olamaz")
        if "valid_until" in update_data:
            await self._check_no_overlap(
                agency_id, obj.brand_id, obj.valid_from, new_valid_until, exclude_id=obj.id
            )

        update_data["updated_by_id"] = actor_id
        updated = await self._repo.update(obj, update_data)
        await self._db.commit()
        await self._db.refresh(updated)
        return updated

    async def get(self, agency_id: uuid.UUID, terms_id: uuid.UUID) -> CommercialTerms:
        obj = await self._repo.get_by_id(terms_id, agency_id)
        if obj is None:
            raise NotFoundError("Ticari koşul", str(terms_id))
        return obj

    async def get_active_for_brand(
        self, agency_id: uuid.UUID, brand_id: uuid.UUID
    ) -> CommercialTerms | None:
        return await self._repo.get_active_for_brand(agency_id, brand_id)

    async def list_for_brand(
        self, agency_id: uuid.UUID, brand_id: uuid.UUID
    ) -> list[CommercialTerms]:
        return await self._repo.list_for_brand(agency_id, brand_id)

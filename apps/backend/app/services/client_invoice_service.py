"""ClientInvoiceService: the money-integrity core of Phase 4 (plan §3/§7).

Snapshot-timing decision (plan §3): `TimeEntry.billing_rate_snapshot_cents`/
`cost_rate_snapshot_cents`/`rate_currency_snapshot` are written exactly once,
at the moment a `TimeEntry` is attached to a `ClientInvoiceLine` inside
`generate_draft` — never at entry creation or lock time. A row whose
`invoiced_at` is already set is immutable and refuses re-selection
(idempotency); `void()` is the only path that clears it, deliberately
reopening the entry for a future invoice.

Invoice numbering: a per-agency sequence (`AgencySettings.invoice_number_seq`)
incremented under `SELECT ... FOR UPDATE` in the same transaction as the
invoice insert — see `generate_draft`'s locked section. This is what makes
concurrent draft-generation calls for the same agency serialize instead of
colliding on the `UniqueConstraint(agency_id, invoice_number)`.

Deliberate v1 simplification (documented, not silently dropped): header
totals are always exactly `sum(line subtotal/discount/tax)` — a
`CommercialTerms.discount_rate_bps` header-level percentage discount is not
yet auto-applied on top of that; only explicit per-line/manual discounts are
wired. This keeps `generate_draft`/`update_draft_lines`/`remove_line` using
one single recomputation invariant instead of two divergent totals formulas.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.csv_safety import escape_csv_cell
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.time_utils import utc_today
from app.models.client_invoice import ClientInvoice, ClientInvoiceLine
from app.models.enums import ClientInvoiceLineSourceType, ClientInvoiceStatus, NotificationEventType
from app.models.time_entry import TimeEntry
from app.repositories.agency_member import AgencyMemberRepository
from app.repositories.agency_settings import AgencySettingsRepository
from app.repositories.brand import BrandRepository
from app.repositories.client_invoice import ClientInvoiceRepository
from app.repositories.commercial_terms import CommercialTermsRepository
from app.repositories.member_cost_rate import MemberCostRateRepository
from app.repositories.time_entry import TimeEntryRepository
from app.schemas.client_invoice import (
    ClientInvoiceDraftCreate,
    ClientInvoiceUpdate,
    ManualInvoiceLineInput,
)
from app.services.agency_settings_service import AgencySettingsService
from app.services.notification_dispatcher import NotificationDispatcher

_EDITABLE_STATUSES = frozenset(
    {ClientInvoiceStatus.DRAFT.value, ClientInvoiceStatus.PENDING_APPROVAL.value}
)
_UNVOIDABLE_STATUSES = frozenset(
    {
        ClientInvoiceStatus.PAID.value,
        ClientInvoiceStatus.PARTIALLY_PAID.value,
        ClientInvoiceStatus.CANCELLED.value,
    }
)


def _round_cents(value: float) -> int:
    return int(round(value))


class ClientInvoiceService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = ClientInvoiceRepository(db)
        self._time_entry_repo = TimeEntryRepository(db)
        self._terms_repo = CommercialTermsRepository(db)
        self._cost_rate_repo = MemberCostRateRepository(db)
        self._settings_repo = AgencySettingsRepository(db)
        self._member_repo = AgencyMemberRepository(db)
        self._brand_repo = BrandRepository(db)

    # ------------------------------------------------------------------
    # Billable time entries
    # ------------------------------------------------------------------

    async def list_billable_time_entries(
        self,
        agency_id: uuid.UUID,
        brand_id: uuid.UUID,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[TimeEntry]:
        """Billable, locked, un-invoiced entries for a brand/period — exactly
        the pool `generate_draft` is allowed to select from."""
        entries = await self._time_entry_repo.list_for_brand(brand_id, agency_id, start, end)
        return [
            e
            for e in entries
            if e.billable and e.locked and e.invoiced_at is None and e.duration_seconds is not None
        ]

    async def _load_and_validate_entries(
        self, agency_id: uuid.UUID, brand_id: uuid.UUID, entry_ids: list[uuid.UUID]
    ) -> list[TimeEntry]:
        entries: list[TimeEntry] = []
        for entry_id in entry_ids:
            entry = await self._time_entry_repo.get_by_id(entry_id, agency_id)
            if entry is None:
                raise NotFoundError("Zaman kaydı", str(entry_id))
            if entry.brand_id != brand_id:
                raise ValidationError("Zaman kaydı seçilen markaya ait değil")
            if not entry.billable:
                raise ValidationError("Faturalandırılamaz (billable=false) zaman kaydı seçildi")
            if not entry.locked:
                raise ValidationError("Kilitlenmemiş zaman kaydı faturalanamaz")
            if entry.duration_seconds is None:
                raise ValidationError("Devam eden (durdurulmamış) zaman kaydı faturalanamaz")
            if entry.invoiced_at is not None:
                raise ConflictError("Bu zaman kaydı zaten bir faturaya eklenmiş")
            if await self._repo.is_time_entry_already_invoiced(entry.id):
                # Defense-in-depth: should be unreachable given the
                # invoiced_at check above, but mirrors the DB partial
                # unique index per plan §3/§12.
                raise ConflictError("Bu zaman kaydı zaten bir faturaya eklenmiş")
            entries.append(entry)
        return entries

    async def _resolve_cost_rate_cents(
        self,
        agency_id: uuid.UUID,
        user_id: uuid.UUID,
        as_of: date,
        cache: dict[uuid.UUID, int | None],
    ) -> int | None:
        if user_id in cache:
            return cache[user_id]
        rate = await self._cost_rate_repo.get_effective_for_user(agency_id, user_id, as_of)
        if rate is None:
            membership = await self._member_repo.get_membership(agency_id, user_id)
            if membership is not None:
                rate = await self._cost_rate_repo.get_effective_for_role(
                    agency_id, membership.role, as_of
                )
        result = rate.hourly_cost_cents if rate is not None else None
        cache[user_id] = result
        return result

    # ------------------------------------------------------------------
    # Draft generation
    # ------------------------------------------------------------------

    async def generate_draft(
        self, agency_id: uuid.UUID, actor_id: uuid.UUID, data: ClientInvoiceDraftCreate
    ) -> ClientInvoice:
        brand = await self._brand_repo.get_by_id_and_agency(data.brand_id, agency_id)
        if brand is None:
            raise NotFoundError("Marka", str(data.brand_id))

        if not data.time_entry_ids and not data.include_fixed_fee and not data.manual_lines:
            raise ValidationError("En az bir fatura kalemi seçilmeli")

        terms = await self._terms_repo.get_active_for_brand(agency_id, data.brand_id)

        issue_date = data.issue_date or utc_today()
        payment_terms_days = terms.payment_terms_days if terms is not None else 30
        due_date = data.due_date or (issue_date + timedelta(days=payment_terms_days))
        if due_date < issue_date:
            raise ValidationError("Vade tarihi fatura tarihinden önce olamaz")

        currency = terms.currency if terms is not None else brand.currency

        lines_payload: list[dict] = []
        entry_snapshots: list[tuple[TimeEntry, dict]] = []

        if data.time_entry_ids:
            if terms is None or terms.hourly_rate_cents is None:
                raise ValidationError(
                    "Zaman kayıtlarını faturalamak için markanın saatlik ücreti tanımlanmış "
                    "aktif bir ticari koşulu olmalı"
                )
            entries = await self._load_and_validate_entries(
                agency_id, data.brand_id, data.time_entry_ids
            )
            cost_rate_cache: dict[uuid.UUID, int | None] = {}
            for entry in entries:
                assert entry.duration_seconds is not None  # validated above
                cost_rate_cents = await self._resolve_cost_rate_cents(
                    agency_id, entry.user_id, issue_date, cost_rate_cache
                )
                hours = entry.duration_seconds / 3600
                subtotal = _round_cents(hours * terms.hourly_rate_cents)
                tax = _round_cents(subtotal * terms.tax_rate_bps / 10000)
                lines_payload.append(
                    {
                        "source_type": ClientInvoiceLineSourceType.TIME_ENTRY.value,
                        "source_id": entry.id,
                        "description": entry.description or f"{entry.category} - zaman kaydı",
                        "quantity": round(hours, 4),
                        "unit": "saat",
                        "unit_price_cents": terms.hourly_rate_cents,
                        "tax_rate_bps": terms.tax_rate_bps,
                        "discount_cents": 0,
                        "subtotal_cents": subtotal,
                        "tax_cents": tax,
                        "total_cents": subtotal + tax,
                        "billing_rate_snapshot_cents": terms.hourly_rate_cents,
                        "cost_rate_snapshot_cents": cost_rate_cents,
                        "service_period_start": entry.started_at.date(),
                        "service_period_end": entry.started_at.date(),
                    }
                )
                entry_snapshots.append(
                    (
                        entry,
                        {
                            "billing_rate_snapshot_cents": terms.hourly_rate_cents,
                            "cost_rate_snapshot_cents": cost_rate_cents,
                            "rate_currency_snapshot": terms.currency,
                        },
                    )
                )

        if data.include_fixed_fee:
            if terms is None or terms.fixed_fee_cents is None:
                raise ValidationError("Markanın sabit ücreti tanımlı değil")
            subtotal = terms.fixed_fee_cents
            tax = _round_cents(subtotal * terms.tax_rate_bps / 10000)
            lines_payload.append(
                {
                    "source_type": ClientInvoiceLineSourceType.FIXED_FEE.value,
                    "source_id": None,
                    "description": "Sabit ücret",
                    "quantity": 1.0,
                    "unit": "proje",
                    "unit_price_cents": subtotal,
                    "tax_rate_bps": terms.tax_rate_bps,
                    "discount_cents": 0,
                    "subtotal_cents": subtotal,
                    "tax_cents": tax,
                    "total_cents": subtotal + tax,
                    "billing_rate_snapshot_cents": None,
                    "cost_rate_snapshot_cents": None,
                    "service_period_start": data.service_period_start,
                    "service_period_end": data.service_period_end,
                }
            )

        for manual in data.manual_lines:
            lines_payload.append(self._build_manual_line_dict(manual))

        header_subtotal = sum(line["subtotal_cents"] for line in lines_payload)
        header_discount = sum(line["discount_cents"] for line in lines_payload)
        header_tax = sum(line["tax_cents"] for line in lines_payload)
        header_total = header_subtotal - header_discount + header_tax
        if header_total < 0:
            raise ValidationError("Fatura toplamı negatif olamaz")

        billing_contact_name = terms.billing_contact_name if terms is not None else None
        billing_contact_email = terms.billing_contact_email if terms is not None else None
        billing_address = terms.billing_address if terms is not None else brand.billing_address
        tax_office = terms.tax_office if terms is not None else brand.tax_office
        tax_number = terms.tax_number if terms is not None else brand.tax_number

        # Ensure the settings row exists (its own committed transaction —
        # safe here since nothing invoice-related has been written yet).
        await AgencySettingsService(self._db).get_or_create(agency_id)

        # ---- locked numbering + invoice insert, single transaction ----
        locked_settings = await self._settings_repo.get_by_agency_for_update(agency_id)
        if locked_settings is None:
            raise NotFoundError("Ajans ayarları", str(agency_id))
        new_seq = locked_settings.invoice_number_seq + 1
        locked_settings.invoice_number_seq = new_seq
        invoice_number = f"{issue_date.year}-{new_seq:06d}"

        invoice = await self._repo.create(
            {
                "agency_id": agency_id,
                "brand_id": data.brand_id,
                "commercial_terms_id": terms.id if terms is not None else None,
                "invoice_number": invoice_number,
                "document_type": data.document_type,
                "issue_date": issue_date,
                "due_date": due_date,
                "service_period_start": data.service_period_start,
                "service_period_end": data.service_period_end,
                "currency": currency,
                "subtotal_cents": header_subtotal,
                "discount_cents": header_discount,
                "tax_cents": header_tax,
                "total_cents": header_total,
                "amount_paid_cents": 0,
                "status": ClientInvoiceStatus.DRAFT.value,
                "notes": data.notes,
                "billing_contact_name": billing_contact_name,
                "billing_contact_email": billing_contact_email,
                "billing_address": billing_address,
                "tax_office": tax_office,
                "tax_number": tax_number,
                "created_by_id": actor_id,
            }
        )

        for line_data in lines_payload:
            line_data["invoice_id"] = invoice.id
            await self._repo.add_line(line_data)

        now = datetime.now(UTC)
        for entry, snapshot in entry_snapshots:
            snapshot["invoiced_at"] = now
            await self._time_entry_repo.update(entry, snapshot)

        await self._db.commit()
        await self._db.refresh(invoice)
        return invoice

    def _build_manual_line_dict(self, manual: ManualInvoiceLineInput) -> dict:
        subtotal = _round_cents(manual.quantity * manual.unit_price_cents)
        if manual.discount_cents > subtotal:
            raise ValidationError("Kalem indirimi ara toplamı aşamaz")
        taxable = subtotal - manual.discount_cents
        tax = _round_cents(taxable * manual.tax_rate_bps / 10000)
        return {
            "source_type": manual.source_type,
            "source_id": manual.source_id,
            "description": manual.description,
            "quantity": manual.quantity,
            "unit": manual.unit,
            "unit_price_cents": manual.unit_price_cents,
            "tax_rate_bps": manual.tax_rate_bps,
            "discount_cents": manual.discount_cents,
            "subtotal_cents": subtotal,
            "tax_cents": tax,
            "total_cents": taxable + tax,
            "billing_rate_snapshot_cents": None,
            "cost_rate_snapshot_cents": None,
            "service_period_start": None,
            "service_period_end": None,
        }

    # ------------------------------------------------------------------
    # Draft editing
    # ------------------------------------------------------------------

    async def add_manual_line(
        self,
        agency_id: uuid.UUID,
        invoice_id: uuid.UUID,
        data: ManualInvoiceLineInput,
    ) -> ClientInvoice:
        invoice = await self._get_or_404(agency_id, invoice_id)
        if invoice.status not in _EDITABLE_STATUSES:
            raise ConflictError("Yalnızca taslak/onay bekleyen faturalara kalem eklenebilir")
        line_data = self._build_manual_line_dict(data)
        line_data["invoice_id"] = invoice.id
        await self._repo.add_line(line_data)
        updated = await self._recompute_totals(invoice)
        await self._db.commit()
        await self._db.refresh(updated)
        return updated

    async def remove_line(
        self, agency_id: uuid.UUID, invoice_id: uuid.UUID, line_id: uuid.UUID
    ) -> ClientInvoice:
        invoice = await self._get_or_404(agency_id, invoice_id)
        if invoice.status not in _EDITABLE_STATUSES:
            raise ConflictError("Yalnızca taslak/onay bekleyen faturalardan kalem silinebilir")
        line = await self._repo.get_line(line_id, invoice.id)
        if line is None:
            raise NotFoundError("Fatura kalemi", str(line_id))
        await self._reopen_line_source_if_time_entry(agency_id, line)
        await self._repo.soft_delete_line(line)
        updated = await self._recompute_totals(invoice)
        await self._db.commit()
        await self._db.refresh(updated)
        return updated

    async def _reopen_line_source_if_time_entry(
        self, agency_id: uuid.UUID, line: ClientInvoiceLine
    ) -> None:
        if line.source_type != ClientInvoiceLineSourceType.TIME_ENTRY.value:
            return
        if line.source_id is None:
            return
        entry = await self._time_entry_repo.get_by_id(line.source_id, agency_id)
        if entry is None:
            return
        await self._time_entry_repo.update(
            entry,
            {
                "invoiced_at": None,
                "billing_rate_snapshot_cents": None,
                "cost_rate_snapshot_cents": None,
                "rate_currency_snapshot": None,
            },
        )

    async def _recompute_totals(self, invoice: ClientInvoice) -> ClientInvoice:
        lines = await self._repo.list_lines(invoice.id)
        subtotal = sum(line.subtotal_cents for line in lines)
        discount = sum(line.discount_cents for line in lines)
        tax = sum(line.tax_cents for line in lines)
        total = subtotal - discount + tax
        return await self._repo.update(
            invoice,
            {
                "subtotal_cents": subtotal,
                "discount_cents": discount,
                "tax_cents": tax,
                "total_cents": total,
            },
        )

    async def update(
        self,
        agency_id: uuid.UUID,
        invoice_id: uuid.UUID,
        data: ClientInvoiceUpdate,
    ) -> ClientInvoice:
        invoice = await self._get_or_404(agency_id, invoice_id)
        if invoice.status not in _EDITABLE_STATUSES:
            raise ConflictError("Yalnızca taslak/onay bekleyen faturalar düzenlenebilir")
        update_data = data.model_dump(exclude_unset=True, exclude_none=True)
        new_due_date = update_data.get("due_date", invoice.due_date)
        if new_due_date < invoice.issue_date:
            raise ValidationError("Vade tarihi fatura tarihinden önce olamaz")
        updated = await self._repo.update(invoice, update_data)
        await self._db.commit()
        await self._db.refresh(updated)
        return updated

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------

    async def approve(
        self, agency_id: uuid.UUID, invoice_id: uuid.UUID, actor_id: uuid.UUID
    ) -> ClientInvoice:
        invoice = await self._get_or_404(agency_id, invoice_id)
        if invoice.status not in _EDITABLE_STATUSES:
            raise ConflictError("Yalnızca taslak/onay bekleyen faturalar onaylanabilir")
        updated = await self._repo.update(
            invoice,
            {
                "status": ClientInvoiceStatus.APPROVED.value,
                "approved_by_id": actor_id,
                "approved_at": datetime.now(UTC),
            },
        )
        await self._db.commit()
        await self._db.refresh(updated)
        return updated

    async def send(self, agency_id: uuid.UUID, invoice_id: uuid.UUID) -> ClientInvoice:
        invoice = await self._get_or_404(agency_id, invoice_id)
        if invoice.status != ClientInvoiceStatus.APPROVED.value:
            raise ConflictError("Yalnızca onaylanmış faturalar gönderilebilir")
        updated = await self._repo.update(
            invoice,
            {"status": ClientInvoiceStatus.SENT.value, "sent_at": datetime.now(UTC)},
        )
        await self._db.commit()
        await self._db.refresh(updated)

        # Notify the brand's own portal users — sending is an agency->client
        # action, so the recipients are the brand's team, not the agency's.
        dispatcher = NotificationDispatcher(self._db)
        brand_recipients = await dispatcher.get_brand_members(updated.brand_id)
        await dispatcher.emit(
            NotificationEventType.INVOICE_SENT.value,
            payload={
                "invoice_id": str(updated.id),
                "invoice_number": updated.invoice_number,
                "due_date": updated.due_date.isoformat(),
                "summary": f"{updated.invoice_number} numaralı fatura size gönderildi.",
            },
            agency_id=agency_id,
            brand_id=updated.brand_id,
            actor_user_id=None,
            recipient_ids=[u.id for u in brand_recipients],
        )
        await self._db.commit()
        return updated

    async def void(self, agency_id: uuid.UUID, invoice_id: uuid.UUID) -> ClientInvoice:
        """Cancels the invoice and reopens every associated `TimeEntry` by
        clearing `invoiced_at` and both rate snapshots (plan §3/§12) — a
        voided invoice must never permanently lock an entry out of future
        billing. Associated lines are soft-deleted so the partial unique
        index on `client_invoice_lines(source_id) WHERE source_type='time_entry'`
        frees up immediately for a future invoice."""
        invoice = await self._get_or_404(agency_id, invoice_id)
        if invoice.status == ClientInvoiceStatus.CANCELLED.value:
            raise ConflictError("Fatura zaten iptal edilmiş")
        if invoice.status in _UNVOIDABLE_STATUSES:
            raise ConflictError("Ödemesi alınmış veya zaten iptal edilmiş fatura iptal edilemez")

        lines = await self._repo.list_lines(invoice.id)
        for line in lines:
            await self._reopen_line_source_if_time_entry(agency_id, line)
            await self._repo.soft_delete_line(line)

        updated = await self._repo.update(
            invoice,
            {"status": ClientInvoiceStatus.CANCELLED.value, "cancelled_at": datetime.now(UTC)},
        )
        await self._db.commit()
        await self._db.refresh(updated)
        return updated

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def _get_or_404(self, agency_id: uuid.UUID, invoice_id: uuid.UUID) -> ClientInvoice:
        invoice = await self._repo.get_by_id(invoice_id, agency_id)
        if invoice is None:
            raise NotFoundError("Fatura", str(invoice_id))
        return invoice

    async def get_with_lines(
        self, agency_id: uuid.UUID, invoice_id: uuid.UUID
    ) -> tuple[ClientInvoice, list[ClientInvoiceLine]]:
        invoice = await self._get_or_404(agency_id, invoice_id)
        lines = await self._repo.list_lines(invoice.id)
        return invoice, lines

    async def list_for_agency(
        self,
        agency_id: uuid.UUID,
        brand_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ClientInvoice]:
        return await self._repo.list_for_agency(agency_id, brand_id, status, limit, offset)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    async def export_csv(self, agency_id: uuid.UUID, invoice_id: uuid.UUID) -> bytes:
        invoice, lines = await self.get_with_lines(agency_id, invoice_id)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "invoice_number",
                "description",
                "quantity",
                "unit",
                "unit_price_cents",
                "discount_cents",
                "tax_rate_bps",
                "subtotal_cents",
                "tax_cents",
                "total_cents",
            ]
        )
        for line in lines:
            writer.writerow(
                [
                    escape_csv_cell(invoice.invoice_number),
                    escape_csv_cell((line.description or "").replace("\n", " ").strip()),
                    line.quantity,
                    escape_csv_cell(line.unit),
                    line.unit_price_cents,
                    line.discount_cents,
                    line.tax_rate_bps,
                    line.subtotal_cents,
                    line.tax_cents,
                    line.total_cents,
                ]
            )
        return buffer.getvalue().encode("utf-8-sig")

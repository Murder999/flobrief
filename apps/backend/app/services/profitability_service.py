"""ProfitabilityService: brief/brand/agency profitability computed at read
time from real, already-persisted data only (plan §7's ProfitabilityService
row, §13). No new "profitability" tables are introduced — every number here
is derived from `ClientInvoice`/`ClientInvoiceLine`, `TimeEntry`'s snapshot
columns, `CommercialTerms`, and `MemberCostRate`, mirroring
`TimeReportService`'s pure-aggregation style.

Snapshot discipline (plan §7, critical): realized cost/revenue for a
TimeEntry-backed line always reads `TimeEntry.billing_rate_snapshot_cents` /
`cost_rate_snapshot_cents` / `rate_currency_snapshot` — the values frozen by
`ClientInvoiceService.generate_draft()` at the moment of invoicing. This
service NEVER re-resolves a "live" `CommercialTerms`/`MemberCostRate` for an
already-invoiced entry; doing so would make a previously-computed
profitability figure silently drift if rates change later, defeating the
entire point of snapshotting. Live rates are read ONLY for two clearly
labeled "tahmini" (estimated/forward-looking) figures that by definition
cannot be snapshotted yet: a brief's planned revenue/cost (from
`Brief.estimated_hours` x current rates) and a brand's unbilled/un-invoiced
WIP valuation.

Missing-rate handling (critical, plan §7/§13): whenever a rate needed for a
cost or margin figure in a given scope (brief/brand-currency/agency-currency)
is unavailable for ANY contributing entry, that scope's cost/margin fields
are returned as `None` with `margin_missing_reason` set — never a
partial/zeroed substitute, which would silently UNDERSTATE cost and so
overstate margin. This is deliberately an all-or-nothing rule per scope, not
a partial sum: a partial sum would look complete without being complete.

Multi-currency safety (plan §7/§13): revenue/cost/WIP are always aggregated
per currency and returned as a list of per-currency breakdowns — brands (or,
at the agency level, an agency's brands) billing in different currencies are
NEVER summed into one blended total anywhere in this module.

COST_RATE_VIEW gating (plan §7/§8/§12): every public method accepts
`include_cost_data: bool`. Revenue/WIP/retainer figures are always computed
and returned regardless; cost/margin figures are computed internally (the
margin math needs them, and risk detection needs them) but are nulled out on
the returned dataclasses, with `cost_data_visible=False`, whenever the
caller lacks `COST_RATE_VIEW` — e.g. a Brand Manager who has
`PROFITABILITY_VIEW` but not `COST_RATE_VIEW` per plan §8's role table.
Margin-derived risk flags ("dusuk_kar_marji"/"negatif_kar_marji") are
likewise stripped from the returned risk-flag list in that case, since their
message text would otherwise leak a margin percentage. This gating is
enforced here, not just at the API layer, so it is directly unit-testable
without going through HTTP.

Configurable-threshold follow-up (documented, not a silent gap): the plan
allows a sensible hardcoded default when no threshold field exists yet.
`_LOW_MARGIN_THRESHOLD_PCT` / `_HIGH_UNBILLED_WIP_HOURS_THRESHOLD` are that
default — a follow-up item is to move these onto `AgencySettings` alongside
its existing capacity thresholds, the same way
`AgencySettings.capacity_*_threshold_pct` already works.

Brief-level revenue attribution limitation (documented, plan §7): only
TimeEntry-backed revenue (via the entry's own snapshot columns) is
attributed to a brief. A `ClientInvoiceLine` of type fixed_fee/retainer/
manual is not tied to a `source_id` that resolves to a brief, so it cannot
be cleanly attributed to one brief among potentially several under the same
brand — this is a documented v1 simplification, not a bug.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.time_utils import utc_today
from app.models.brief import Brief
from app.models.client_invoice import ClientInvoice
from app.models.enums import (
    ClientInvoiceLineSourceType,
    ClientInvoiceStatus,
    CommercialTermsBillingModel,
)
from app.models.time_entry import TimeEntry
from app.repositories.agency_member import AgencyMemberRepository
from app.repositories.brand import BrandRepository
from app.repositories.brief import BriefAssigneeRepository, BriefRepository
from app.repositories.client_invoice import ClientInvoiceRepository
from app.repositories.commercial_terms import CommercialTermsRepository
from app.repositories.member_cost_rate import MemberCostRateRepository
from app.repositories.time_entry import TimeEntryRepository
from app.services.retainer_service import RetainerService

_COST_RATE_MISSING_REASON = "cost_rate_eksik"
_BILLING_RATE_MISSING_REASON = "fiyatlandirma_eksik"

# Follow-up: move onto AgencySettings (see module docstring).
_LOW_MARGIN_THRESHOLD_PCT = 20.0
_HIGH_UNBILLED_WIP_HOURS_THRESHOLD = 80.0

_LOW_MARGIN_RISK = "dusuk_kar_marji"
_NEGATIVE_MARGIN_RISK = "negatif_kar_marji"
_RETAINER_OVERAGE_RISK = "retainer_asimi"
_HIGH_WIP_RISK = "yuksek_faturalanmamis_is"
_OVERDUE_INVOICE_RISK = "gecikmis_fatura"
_COST_DERIVED_RISK_TYPES = frozenset({_LOW_MARGIN_RISK, _NEGATIVE_MARGIN_RISK})

_NON_REALIZED_INVOICE_STATUSES = (
    ClientInvoiceStatus.DRAFT.value,
    ClientInvoiceStatus.CANCELLED.value,
)
_OVERDUE_EXCLUDED_STATUSES = (
    ClientInvoiceStatus.DRAFT.value,
    ClientInvoiceStatus.CANCELLED.value,
    ClientInvoiceStatus.PAID.value,
    ClientInvoiceStatus.FAILED.value,
)


def _round_cents(value: float) -> int:
    return int(round(value))


def _hours(entries: list[TimeEntry]) -> float:
    return round(sum(e.duration_seconds or 0 for e in entries) / 3600, 4)


def _is_overdue(invoice: ClientInvoice, as_of: date) -> bool:
    if invoice.status == ClientInvoiceStatus.OVERDUE.value:
        return True
    if invoice.status in _OVERDUE_EXCLUDED_STATUSES:
        return False
    return invoice.due_date < as_of


def _filter_risk_flags(flags: list[RiskFlag], include_cost_data: bool) -> list[RiskFlag]:
    if include_cost_data:
        return flags
    return [f for f in flags if f.type not in _COST_DERIVED_RISK_TYPES]


@dataclass(frozen=True)
class RiskFlag:
    type: str
    message: str
    brand_id: uuid.UUID | None = None
    brief_id: uuid.UUID | None = None


@dataclass(frozen=True)
class BriefEstimated:
    currency: str | None
    estimated_hours: float | None
    revenue_cents: int | None
    cost_cents: int | None
    gross_profit_cents: int | None
    gross_margin_pct: float | None
    billing_rate_missing: bool
    cost_data_visible: bool
    margin_missing_reason: str | None


@dataclass(frozen=True)
class BriefRealizedCurrency:
    currency: str
    invoiced_hours: float
    revenue_cents: int
    cost_cents: int | None
    gross_profit_cents: int | None
    gross_margin_pct: float | None
    cost_data_visible: bool
    margin_missing_reason: str | None


@dataclass(frozen=True)
class BriefProfitability:
    brief_id: uuid.UUID
    brief_title: str
    brand_id: uuid.UUID | None
    realized: list[BriefRealizedCurrency]
    estimated: BriefEstimated | None
    note: str


@dataclass(frozen=True)
class RetainerUtilization:
    period_start: date
    period_end: date
    included_minutes: int
    used_minutes: int
    remaining_minutes: int
    overage_minutes: int
    overage_cost_cents: int
    currency: str


@dataclass(frozen=True)
class BrandCurrencyFinancials:
    currency: str
    invoiced_revenue_cents: int
    unbilled_wip_cents: int | None
    unbilled_wip_hours: float
    billing_rate_missing_for_wip: bool
    internal_cost_cents: int | None
    gross_profit_cents: int | None
    gross_margin_pct: float | None
    cost_data_visible: bool
    margin_missing_reason: str | None


@dataclass(frozen=True)
class BrandProfitability:
    brand_id: uuid.UUID
    brand_name: str
    period_start: date | None
    period_end: date | None
    currencies: list[BrandCurrencyFinancials]
    retainer: RetainerUtilization | None
    risk_flags: list[RiskFlag]


@dataclass(frozen=True)
class AgencyCurrencyOverview:
    currency: str
    invoiced_revenue_cents: int
    unbilled_wip_cents: int
    internal_cost_cents: int | None
    gross_profit_cents: int | None
    average_margin_pct: float | None
    overdue_receivables_cents: int
    cost_data_visible: bool
    cost_rate_missing: bool


@dataclass(frozen=True)
class AgencyProfitabilityOverview:
    period_start: date | None
    period_end: date | None
    currencies: list[AgencyCurrencyOverview]
    risk_flags: list[RiskFlag]


@dataclass
class _RawCurrencyFinancials:
    """Internal-only, always-full-visibility intermediate — risk detection
    and the public (possibly cost-gated) dataclasses are both derived from
    this, so gating never has to re-derive numbers from scratch."""

    currency: str
    revenue_cents: int
    cost_known: bool
    cost_cents: int
    gross_profit_cents: int | None
    margin_pct: float | None
    unbilled_wip_cents: int | None
    unbilled_wip_hours: float
    wip_billing_rate_missing: bool


class ProfitabilityService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._brief_repo = BriefRepository(db)
        self._assignee_repo = BriefAssigneeRepository(db)
        self._brand_repo = BrandRepository(db)
        self._terms_repo = CommercialTermsRepository(db)
        self._cost_rate_repo = MemberCostRateRepository(db)
        self._member_repo = AgencyMemberRepository(db)
        self._time_entry_repo = TimeEntryRepository(db)
        self._invoice_repo = ClientInvoiceRepository(db)

    async def _resolve_cost_rate_cents(
        self,
        agency_id: uuid.UUID,
        user_id: uuid.UUID,
        as_of: date,
        cache: dict[uuid.UUID, int | None],
    ) -> int | None:
        """Mirrors `ClientInvoiceService._resolve_cost_rate_cents` — user
        rate first, role-fallback second. Only used for forward-looking
        ("tahmini") estimates and WIP; realized figures never call this,
        they read the frozen snapshot instead."""
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
    # Brief-level
    # ------------------------------------------------------------------

    async def get_brief_profitability(
        self,
        agency_id: uuid.UUID,
        brief_id: uuid.UUID,
        *,
        include_cost_data: bool = True,
        as_of: date | None = None,
    ) -> BriefProfitability:
        brief = await self._brief_repo.get_by_id(brief_id, agency_id)
        if brief is None:
            raise NotFoundError("Brief", str(brief_id))
        as_of = as_of or utc_today()

        entries = await self._time_entry_repo.list_for_brief(brief_id, agency_id)
        invoiced = [
            e for e in entries if e.invoiced_at is not None and e.duration_seconds is not None
        ]

        by_currency: dict[str, list[TimeEntry]] = {}
        for e in invoiced:
            currency = e.rate_currency_snapshot or "BILINMEYEN"
            by_currency.setdefault(currency, []).append(e)

        realized: list[BriefRealizedCurrency] = []
        for currency, group in sorted(by_currency.items()):
            revenue_cents = 0
            cost_cents = 0
            cost_known = True
            for e in group:
                hours = e.duration_seconds / 3600  # type: ignore[operator]
                if e.billing_rate_snapshot_cents is not None:
                    revenue_cents += _round_cents(hours * e.billing_rate_snapshot_cents)
                if e.cost_rate_snapshot_cents is None:
                    cost_known = False
                else:
                    cost_cents += _round_cents(hours * e.cost_rate_snapshot_cents)

            gross_profit = None
            margin_pct = None
            reason = None
            if not cost_known:
                reason = _COST_RATE_MISSING_REASON
            else:
                gross_profit = revenue_cents - cost_cents
                margin_pct = (
                    round(gross_profit / revenue_cents * 100, 2) if revenue_cents > 0 else None
                )

            realized.append(
                BriefRealizedCurrency(
                    currency=currency,
                    invoiced_hours=_hours(group),
                    revenue_cents=revenue_cents,
                    cost_cents=(cost_cents if cost_known and include_cost_data else None),
                    gross_profit_cents=(gross_profit if include_cost_data else None),
                    gross_margin_pct=(margin_pct if include_cost_data else None),
                    cost_data_visible=include_cost_data,
                    margin_missing_reason=(reason if include_cost_data else None),
                )
            )

        estimated = await self._estimate_brief(agency_id, brief, as_of, include_cost_data)

        return BriefProfitability(
            brief_id=brief.id,
            brief_title=brief.title,
            brand_id=brief.brand_id,
            realized=realized,
            estimated=estimated,
            note=(
                "Gerçekleşen gelir yalnızca bu brief'e bağlı faturalanmış zaman "
                "kayıtlarından hesaplanır; sabit ücret/retainer fatura kalemleri "
                "belirli bir brief'e atfedilemediği için bu hesaplamaya dahil "
                "edilmemiştir (v1 sınırlaması)."
            ),
        )

    async def _estimate_brief(
        self,
        agency_id: uuid.UUID,
        brief: Brief,
        as_of: date,
        include_cost_data: bool,
    ) -> BriefEstimated | None:
        if brief.estimated_hours is None or brief.brand_id is None:
            return None

        terms = await self._terms_repo.get_active_for_brand(agency_id, brief.brand_id)
        currency = terms.currency if terms is not None else None
        billing_rate_missing = terms is None or terms.hourly_rate_cents is None
        revenue_cents = None
        if not billing_rate_missing:
            assert terms is not None and terms.hourly_rate_cents is not None
            revenue_cents = _round_cents(brief.estimated_hours * terms.hourly_rate_cents)

        assignees = await self._assignee_repo.get_for_brief(brief.id)
        cost_cents: int | None = None
        cost_known = False
        if assignees:
            per_assignee_hours = brief.estimated_hours / len(assignees)
            cache: dict[uuid.UUID, int | None] = {}
            total = 0
            all_known = True
            for assignee in assignees:
                rate = await self._resolve_cost_rate_cents(
                    agency_id, assignee.user_id, as_of, cache
                )
                if rate is None:
                    all_known = False
                    continue
                total += _round_cents(per_assignee_hours * rate)
            if all_known:
                cost_cents = total
                cost_known = True

        gross_profit = None
        margin_pct = None
        reason = None
        if billing_rate_missing:
            reason = _BILLING_RATE_MISSING_REASON
        elif not cost_known:
            reason = _COST_RATE_MISSING_REASON
        else:
            assert revenue_cents is not None and cost_cents is not None
            gross_profit = revenue_cents - cost_cents
            margin_pct = round(gross_profit / revenue_cents * 100, 2) if revenue_cents > 0 else None

        if include_cost_data:
            shown_reason = reason
        else:
            shown_reason = _BILLING_RATE_MISSING_REASON if billing_rate_missing else None

        return BriefEstimated(
            currency=currency,
            estimated_hours=brief.estimated_hours,
            revenue_cents=revenue_cents,
            cost_cents=(cost_cents if include_cost_data else None),
            gross_profit_cents=(gross_profit if include_cost_data else None),
            gross_margin_pct=(margin_pct if include_cost_data else None),
            billing_rate_missing=billing_rate_missing,
            cost_data_visible=include_cost_data,
            margin_missing_reason=shown_reason,
        )

    # ------------------------------------------------------------------
    # Brand-level
    # ------------------------------------------------------------------

    async def get_brand_profitability(
        self,
        agency_id: uuid.UUID,
        brand_id: uuid.UUID,
        *,
        start: date | None = None,
        end: date | None = None,
        include_cost_data: bool = True,
        as_of: date | None = None,
    ) -> BrandProfitability:
        brand = await self._brand_repo.get_by_id_and_agency(brand_id, agency_id)
        if brand is None:
            raise NotFoundError("Marka", str(brand_id))
        as_of = as_of or utc_today()

        invoices = await self._invoice_repo.list_for_period(
            agency_id, brand_id, start, end, exclude_statuses=_NON_REALIZED_INVOICE_STATUSES
        )
        invoice_ids = [inv.id for inv in invoices]
        lines = await self._invoice_repo.list_lines_for_invoices(invoice_ids)
        lines_by_invoice: dict[uuid.UUID, list] = {}
        for line in lines:
            lines_by_invoice.setdefault(line.invoice_id, []).append(line)

        revenue_by_currency: dict[str, int] = {}
        cost_by_currency: dict[str, int] = {}
        cost_complete_by_currency: dict[str, bool] = {}
        for inv in invoices:
            revenue_by_currency[inv.currency] = (
                revenue_by_currency.get(inv.currency, 0) + inv.total_cents
            )
            cost_complete_by_currency.setdefault(inv.currency, True)
            for line in lines_by_invoice.get(inv.id, []):
                if (
                    line.source_type == ClientInvoiceLineSourceType.TIME_ENTRY.value
                    and line.cost_rate_snapshot_cents is not None
                ):
                    cost_by_currency[inv.currency] = cost_by_currency.get(
                        inv.currency, 0
                    ) + _round_cents(line.quantity * line.cost_rate_snapshot_cents)
                elif line.total_cents:
                    # Fixed-fee/retainer/manual lines, or a time-entry line
                    # whose cost rate was missing at invoicing time, have no
                    # known cost basis -> this currency's cost total is
                    # incomplete for the whole scope (never assumed zero).
                    cost_complete_by_currency[inv.currency] = False

        # Unbilled billable WIP, priced at the brand's CURRENT active terms
        # (plan §7) — a forward-looking figure, deliberately separate from
        # realized revenue above and never included in it.
        wip_entries = await self._time_entry_repo.list_for_brand(brand_id, agency_id)
        unbilled = [
            e
            for e in wip_entries
            if e.billable and e.locked and e.invoiced_at is None and e.duration_seconds is not None
        ]
        terms = await self._terms_repo.get_active_for_brand(agency_id, brand_id)
        wip_currency = terms.currency if terms is not None else brand.currency
        wip_hours = _hours(unbilled)
        wip_billing_rate_missing = terms is None or terms.hourly_rate_cents is None
        wip_cents = None
        if not wip_billing_rate_missing:
            assert terms is not None and terms.hourly_rate_cents is not None
            wip_cents = _round_cents(wip_hours * terms.hourly_rate_cents)

        currencies = sorted(set(revenue_by_currency) | {wip_currency})
        raw: list[_RawCurrencyFinancials] = []
        for currency in currencies:
            revenue_cents = revenue_by_currency.get(currency, 0)
            cost_known = cost_complete_by_currency.get(currency, True)
            cost_cents = cost_by_currency.get(currency, 0)
            gross_profit = None
            margin_pct = None
            if cost_known:
                gross_profit = revenue_cents - cost_cents
                margin_pct = (
                    round(gross_profit / revenue_cents * 100, 2) if revenue_cents > 0 else None
                )
            raw.append(
                _RawCurrencyFinancials(
                    currency=currency,
                    revenue_cents=revenue_cents,
                    cost_known=cost_known,
                    cost_cents=cost_cents,
                    gross_profit_cents=gross_profit,
                    margin_pct=margin_pct,
                    unbilled_wip_cents=(wip_cents if currency == wip_currency else None),
                    unbilled_wip_hours=(wip_hours if currency == wip_currency else 0.0),
                    wip_billing_rate_missing=(
                        wip_billing_rate_missing if currency == wip_currency else False
                    ),
                )
            )

        retainer = None
        if terms is not None and terms.billing_model == CommercialTermsBillingModel.RETAINER.value:
            try:
                summary = await RetainerService(self._db).get_current_period_summary(
                    agency_id, brand_id, as_of
                )
                retainer = RetainerUtilization(
                    period_start=summary.period_start,
                    period_end=summary.period_end,
                    included_minutes=summary.included_minutes,
                    used_minutes=summary.used_minutes,
                    remaining_minutes=summary.remaining_minutes,
                    overage_minutes=summary.overage_minutes,
                    overage_cost_cents=summary.overage_cost_cents,
                    currency=summary.currency,
                )
            except ValidationError:
                retainer = None

        overdue_invoices = await self._invoice_repo.list_for_period(
            agency_id, brand_id, None, None, exclude_statuses=_OVERDUE_EXCLUDED_STATUSES
        )

        risk_flags = _filter_risk_flags(
            self._detect_brand_risks(brand_id, raw, retainer, overdue_invoices, as_of),
            include_cost_data,
        )

        public_currencies = [
            BrandCurrencyFinancials(
                currency=r.currency,
                invoiced_revenue_cents=r.revenue_cents,
                unbilled_wip_cents=r.unbilled_wip_cents,
                unbilled_wip_hours=r.unbilled_wip_hours,
                billing_rate_missing_for_wip=r.wip_billing_rate_missing,
                internal_cost_cents=(r.cost_cents if r.cost_known and include_cost_data else None),
                gross_profit_cents=(r.gross_profit_cents if include_cost_data else None),
                gross_margin_pct=(r.margin_pct if include_cost_data else None),
                cost_data_visible=include_cost_data,
                margin_missing_reason=(
                    _COST_RATE_MISSING_REASON if include_cost_data and not r.cost_known else None
                ),
            )
            for r in raw
        ]

        return BrandProfitability(
            brand_id=brand.id,
            brand_name=brand.name,
            period_start=start,
            period_end=end,
            currencies=public_currencies,
            retainer=retainer,
            risk_flags=risk_flags,
        )

    def _detect_brand_risks(
        self,
        brand_id: uuid.UUID,
        raw: list[_RawCurrencyFinancials],
        retainer: RetainerUtilization | None,
        overdue_invoices: list[ClientInvoice],
        as_of: date,
    ) -> list[RiskFlag]:
        flags: list[RiskFlag] = []
        for r in raw:
            if r.cost_known and r.margin_pct is not None:
                if r.margin_pct < 0:
                    flags.append(
                        RiskFlag(
                            type=_NEGATIVE_MARGIN_RISK,
                            brand_id=brand_id,
                            message=f"{r.currency} için brüt kar marjı negatif (%{r.margin_pct})",
                        )
                    )
                elif r.margin_pct < _LOW_MARGIN_THRESHOLD_PCT:
                    flags.append(
                        RiskFlag(
                            type=_LOW_MARGIN_RISK,
                            brand_id=brand_id,
                            message=f"{r.currency} için brüt kar marjı düşük (%{r.margin_pct})",
                        )
                    )
            if r.unbilled_wip_hours > _HIGH_UNBILLED_WIP_HOURS_THRESHOLD:
                flags.append(
                    RiskFlag(
                        type=_HIGH_WIP_RISK,
                        brand_id=brand_id,
                        message=(
                            f"{r.currency} için faturalanmamış iş yükü yüksek "
                            f"({r.unbilled_wip_hours} saat)"
                        ),
                    )
                )
        if retainer is not None and retainer.overage_minutes > 0:
            flags.append(
                RiskFlag(
                    type=_RETAINER_OVERAGE_RISK,
                    brand_id=brand_id,
                    message=f"Retainer aşımı: {retainer.overage_minutes} dakika",
                )
            )
        for inv in overdue_invoices:
            if _is_overdue(inv, as_of):
                flags.append(
                    RiskFlag(
                        type=_OVERDUE_INVOICE_RISK,
                        brand_id=brand_id,
                        message=f"{inv.invoice_number} numaralı fatura vadesi geçmiş",
                    )
                )
        return flags

    # ------------------------------------------------------------------
    # Agency-level overview
    # ------------------------------------------------------------------

    async def get_agency_overview(
        self,
        agency_id: uuid.UUID,
        *,
        start: date | None = None,
        end: date | None = None,
        include_cost_data: bool = True,
        as_of: date | None = None,
    ) -> AgencyProfitabilityOverview:
        as_of = as_of or utc_today()
        brands = await self._brand_repo.list_by_agency(agency_id)

        totals: dict[str, dict[str, float | int | bool]] = {}
        risk_flags: list[RiskFlag] = []

        for brand in brands:
            brand_result = await self.get_brand_profitability(
                agency_id,
                brand.id,
                start=start,
                end=end,
                include_cost_data=True,  # compute in full internally; gate once below
                as_of=as_of,
            )
            risk_flags.extend(brand_result.risk_flags)
            for cf in brand_result.currencies:
                bucket = totals.setdefault(
                    cf.currency,
                    {"revenue": 0, "wip": 0, "cost": 0, "cost_known": True},
                )
                bucket["revenue"] = int(bucket["revenue"]) + cf.invoiced_revenue_cents
                if cf.unbilled_wip_cents is not None:
                    bucket["wip"] = int(bucket["wip"]) + cf.unbilled_wip_cents
                if cf.margin_missing_reason == _COST_RATE_MISSING_REASON:
                    bucket["cost_known"] = False
                if cf.internal_cost_cents is not None:
                    bucket["cost"] = int(bucket["cost"]) + cf.internal_cost_cents

        overdue_invoices = await self._invoice_repo.list_for_period(
            agency_id, None, None, None, exclude_statuses=_OVERDUE_EXCLUDED_STATUSES
        )
        overdue_by_currency: dict[str, int] = {}
        for inv in overdue_invoices:
            if _is_overdue(inv, as_of):
                overdue_by_currency[inv.currency] = overdue_by_currency.get(inv.currency, 0) + (
                    inv.total_cents - inv.amount_paid_cents
                )

        currencies: list[AgencyCurrencyOverview] = []
        for currency, bucket in sorted(totals.items()):
            revenue_cents = int(bucket["revenue"])
            wip_cents = int(bucket["wip"])
            cost_known = bool(bucket["cost_known"])
            cost_cents = int(bucket["cost"]) if cost_known else None
            gross_profit = None
            avg_margin = None
            if cost_known:
                gross_profit = revenue_cents - int(bucket["cost"])
                avg_margin = (
                    round(gross_profit / revenue_cents * 100, 2) if revenue_cents > 0 else None
                )
            currencies.append(
                AgencyCurrencyOverview(
                    currency=currency,
                    invoiced_revenue_cents=revenue_cents,
                    unbilled_wip_cents=wip_cents,
                    internal_cost_cents=(cost_cents if include_cost_data else None),
                    gross_profit_cents=(gross_profit if include_cost_data else None),
                    average_margin_pct=(avg_margin if include_cost_data else None),
                    overdue_receivables_cents=overdue_by_currency.get(currency, 0),
                    cost_data_visible=include_cost_data,
                    cost_rate_missing=not cost_known,
                )
            )

        return AgencyProfitabilityOverview(
            period_start=start,
            period_end=end,
            currencies=currencies,
            risk_flags=_filter_risk_flags(risk_flags, include_cost_data),
        )

// Shared helpers for the finance settings pages (`app/dashboard/finance/**`,
// `components/finance/**`). Labels/currency list mirror the conventions in
// apps/backend/app/schemas/commercial_terms.py and
// apps/backend/app/schemas/member_cost_rate.py — the curated ISO 4217
// allowlist here must stay in sync with `_VALID_CURRENCIES` in both.

import type {
  AccountingProviderValue,
  ClientInvoiceDocumentTypeValue,
  ClientInvoiceStatusValue,
  CommercialTermsBillingModelValue,
  ConnectorStatusValue,
  MarginMissingReasonValue,
  PaymentMethodValue,
} from "./api-client";

export const FINANCE_CURRENCIES = [
  "TRY", "USD", "EUR", "GBP", "CHF", "JPY", "CAD", "AUD", "SEK", "NOK",
  "DKK", "PLN", "CZK", "HUF", "RON", "BGN", "RUB", "AED", "SAR", "QAR",
  "KWD", "ILS", "CNY", "HKD", "SGD", "INR", "ZAR", "BRL", "MXN", "AZN",
] as const;

export const BILLING_MODEL_LABEL: Record<CommercialTermsBillingModelValue, string> = {
  hourly: "Saatlik",
  fixed_fee: "Sabit Ücret",
  retainer: "Retainer (Aylık Paket)",
  per_item: "Birim Başına",
  hybrid: "Karma",
};

export const BILLING_MODEL_DESCRIPTION: Record<CommercialTermsBillingModelValue, string> = {
  hourly: "Yalnızca çalışılan saat üzerinden faturalandırılır.",
  fixed_fee: "Proje için sabit bir toplam ücret uygulanır.",
  retainer: "Aylık sabit tutar; dahil dakika ve aşım oranı içerir.",
  per_item: "Teslim edilen içerik/adet başına ücretlendirilir.",
  hybrid: "Saatlik ücret diğer modellerden biriyle birlikte kullanılır.",
};

/** Which money fields are relevant for a given billing model — drives
 * conditional field visibility in `CommercialTermsForm`. Mirrors how the
 * backend leaves the irrelevant `..._cents` columns null rather than
 * rejecting them (no server-side cross-field requirement per model), but
 * showing every field regardless of model would be confusing. */
export const BILLING_MODEL_FIELDS: Record<
  CommercialTermsBillingModelValue,
  Array<"hourly_rate_cents" | "fixed_fee_cents" | "retainer_amount_cents" | "retainer_included_minutes" | "overage_rate_cents" | "per_item_rate_cents">
> = {
  hourly: ["hourly_rate_cents"],
  fixed_fee: ["fixed_fee_cents"],
  retainer: ["retainer_amount_cents", "retainer_included_minutes", "overage_rate_cents"],
  per_item: ["per_item_rate_cents"],
  hybrid: ["hourly_rate_cents", "fixed_fee_cents", "retainer_amount_cents", "retainer_included_minutes", "overage_rate_cents", "per_item_rate_cents"],
};

/** cents (integer) → localized currency string, e.g. 150000 + "TRY" ->
 * "₺1.500,00". Same approach as the local `formatCents` helper in
 * app/dashboard/settings/billing/page.tsx, centralized here since multiple
 * finance components need it. */
export function formatMoneyCents(cents: number | null | undefined, currency: string): string {
  if (cents === null || cents === undefined) return "—";
  const locale = currency === "TRY" ? "tr-TR" : "en-US";
  try {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency,
      minimumFractionDigits: 2,
    }).format(cents / 100);
  } catch {
    return `${(cents / 100).toFixed(2)} ${currency}`;
  }
}

/** Whole-currency-unit form input (e.g. "1500.00") → integer cents for the
 * API. Money is always `..._cents` server-side (plan §2) — forms only ever
 * work in whole units for the user. Returns null for an empty/invalid
 * input so optional money fields can be omitted. */
export function unitsToCents(value: string): number | null {
  if (value.trim() === "") return null;
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  return Math.round(n * 100);
}

export function centsToUnits(cents: number | null | undefined): string {
  if (cents === null || cents === undefined) return "";
  return String(cents / 100);
}

// AgencyMemberRole values valid as a MemberCostRate `role` target — mirrors
// app.models.enums.AgencyMemberRole (agency-side roles only; brand-portal
// roles are never valid cost-rate targets).
export const COST_RATE_ROLE_OPTIONS = [
  "owner", "admin", "brand_manager", "designer", "developer",
  "social_media_manager", "viewer",
] as const;

/** Percent string (e.g. "20" for 20%) -> basis points (2000), matching
 * `tax_rate_bps`/`discount_rate_bps` server-side (range 0-10000 = 0-100%). */
export function pctToBps(value: string): number | null {
  if (value.trim() === "") return null;
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  return Math.round(n * 100);
}

export function bpsToPct(bps: number | null | undefined): string {
  if (bps === null || bps === undefined) return "";
  return String(bps / 100);
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("tr-TR");
}

// ── RBAC hints (frontend UX only) ───────────────────────────────────────────
// Mirrors the *actual* role -> permission wiring in
// apps/backend/app/core/rbac.py `_AGENCY_ROLE_PERMISSIONS` for the finance
// permission set (plan §8). The backend's `require_permission` dependency
// is the real gate, never this — these only drive which controls render.

const COMMERCIAL_TERMS_MANAGE_ROLES = new Set(["owner", "admin"]);
// COST_RATE_VIEW/MANAGE go to Owner only — no other role, not even Admin
// (plan §8's explicit conservative default; see
// MemberCostRateService._FINANCE_VISIBLE_ROLES server-side).
const COST_RATE_VISIBLE_ROLES = new Set(["owner"]);

export function canManageCommercialTerms(role: string | null | undefined): boolean {
  return !!role && COMMERCIAL_TERMS_MANAGE_ROLES.has(role);
}

export function canViewCostRates(role: string | null | undefined): boolean {
  return !!role && COST_RATE_VISIBLE_ROLES.has(role);
}

// ── Client invoicing (Phase 4) ──────────────────────────────────────────────
// Mirrors ClientInvoiceStatus / ClientInvoiceDocumentType in
// apps/backend/app/models/enums.py. Status is never rendered as a raw enum
// value or color alone anywhere in the invoice UI — always icon + Turkish
// text (mirrors the CapacityStatusBadge product rule).

export const INVOICE_STATUS_LABEL: Record<ClientInvoiceStatusValue, string> = {
  draft: "Taslak",
  pending_approval: "Onay Bekliyor",
  approved: "Onaylandı",
  sending: "Gönderiliyor",
  sent: "Gönderildi",
  partially_paid: "Kısmen Ödendi",
  paid: "Ödendi",
  overdue: "Gecikti",
  cancelled: "İptal",
  failed: "Hata",
};

export const INVOICE_STATUS_COLOR: Record<ClientInvoiceStatusValue, string> = {
  draft: "text-text-muted",
  pending_approval: "text-warning",
  approved: "text-info",
  sending: "text-info",
  sent: "text-accent",
  partially_paid: "text-warning",
  paid: "text-success",
  overdue: "text-danger",
  cancelled: "text-text-muted",
  failed: "text-danger",
};

/** Never "e-fatura" or any wording implying a legally-valid Turkish
 * e-invoice (plan §1/§3/§12) — these are internal draft/proforma documents
 * only, and the UI copy must carry that through every surface, not just
 * the PDF footer. */
export const DOCUMENT_TYPE_LABEL: Record<ClientInvoiceDocumentTypeValue, string> = {
  draft_invoice: "Fatura Taslağı",
  proforma: "Proforma",
};

// RBAC hints for the invoice lifecycle — mirrors plan §8's
// INVOICE_CREATE/APPROVE/VOID wiring (Owner + Admin; Brand Manager is
// INVOICE_VIEW-only). The backend `require_permission` dependency is the
// real gate; these only drive which action buttons render.
const INVOICE_MANAGE_ROLES = new Set(["owner", "admin"]);

export function canManageInvoices(role: string | null | undefined): boolean {
  return !!role && INVOICE_MANAGE_ROLES.has(role);
}

// ── Accounting connectors + payments (Phase 5) ──────────────────────────────
// Mirrors ConnectorStatus/AccountingProvider/PaymentMethod in
// apps/backend/app/models/enums.py. Connector status is never rendered as a
// raw enum value or color alone — always icon + Turkish text
// (`ConnectorStatusBadge`, mirrors the `InvoiceStatusBadge`/
// `CapacityStatusBadge` product rule).

/** Only `manual` has a real implementation server-side (plan §10) — every
 * other `AccountingProvider` enum value exists purely for future UI/schema
 * readiness. The provider `<Select>` in `ConnectorConfigForm` disables
 * every option not in this set, so a user can never pick a provider that
 * would only fail with a 501 after submission. */
export const REAL_ACCOUNTING_PROVIDERS = new Set<AccountingProviderValue>(["manual"]);

export const ACCOUNTING_PROVIDER_LABEL: Record<AccountingProviderValue, string> = {
  manual: "Manuel",
  quickbooks: "QuickBooks",
  xero: "Xero",
  logo: "Logo",
  parasut: "Paraşüt",
  mikro: "Mikro",
};

export const CONNECTOR_STATUS_LABEL: Record<ConnectorStatusValue, string> = {
  not_configured: "Yapılandırılmadı",
  connected: "Bağlı",
  error: "Hata",
};

export const CONNECTOR_STATUS_COLOR: Record<ConnectorStatusValue, string> = {
  not_configured: "text-text-muted",
  connected: "text-success",
  error: "text-danger",
};

export const PAYMENT_METHOD_LABEL: Record<PaymentMethodValue, string> = {
  bank_transfer: "Banka Havalesi",
  credit_card: "Kredi Kartı",
  cash: "Nakit",
  other: "Diğer",
};

// RBAC hints — mirrors plan §8's ACCOUNTING_INTEGRATION_MANAGE (Owner-only,
// not even Admin) and PAYMENT_VIEW/PAYMENT_MANAGE (Owner + Admin) wiring.
// The backend `require_permission` dependency is the real gate; these only
// drive which controls render.
const CONNECTOR_MANAGE_ROLES = new Set(["owner"]);
const PAYMENT_ROLES = new Set(["owner", "admin"]);

export function canManageConnectors(role: string | null | undefined): boolean {
  return !!role && CONNECTOR_MANAGE_ROLES.has(role);
}

export function canViewPayments(role: string | null | undefined): boolean {
  return !!role && PAYMENT_ROLES.has(role);
}

export function canManagePayments(role: string | null | undefined): boolean {
  return !!role && PAYMENT_ROLES.has(role);
}

// ── Profitability (Phase 6) ─────────────────────────────────────────────────
// Mirrors `_COST_RATE_MISSING_REASON`/`_BILLING_RATE_MISSING_REASON` and the
// `RiskFlag.type` string constants in
// apps/backend/app/services/profitability_service.py exactly. A missing
// cost/billing rate is ALWAYS surfaced through `costMissingInfo()` below —
// every profitability UI surface renders its result instead of a number
// whenever it is non-null, never a bare 0, "-", or an omitted field (any of
// which could be misread as an actual zero cost/margin).

export const MARGIN_MISSING_REASON_LABEL: Record<MarginMissingReasonValue, string> = {
  cost_rate_eksik: "Maliyet oranı eksik",
  fiyatlandirma_eksik: "Fiyatlandırma eksik",
};

export const PROFITABILITY_RISK_LABEL: Record<string, string> = {
  dusuk_kar_marji: "Düşük Kâr Marjı",
  negatif_kar_marji: "Negatif Kâr Marjı",
  retainer_asimi: "Retainer Aşımı",
  yuksek_faturalanmamis_is: "Yüksek Faturalanmamış İş",
  gecikmis_fatura: "Gecikmiş Fatura",
};

export function formatPct(pct: number | null | undefined): string {
  if (pct === null || pct === undefined) return "—";
  return `%${pct.toFixed(1)}`;
}

export interface CostVisibilityInput {
  costDataVisible: boolean;
  marginMissingReason?: MarginMissingReasonValue | null;
  costRateMissing?: boolean;
}

export interface CostMissingInfo {
  label: string;
  /** true = hidden because the viewer lacks COST_RATE_VIEW (permission);
   * false = the number is genuinely absent (no cost rate / no billing
   * rate configured yet). Drives which icon renders (Lock vs
   * AlertTriangle) — the two cases must never look identical, since one is
   * "ask an Owner" and the other is "configure a rate". */
  hidden: boolean;
}

/** Single source of truth for whether a cost/margin cell should render a
 * real number or an explicit missing-data label — used by
 * `ProfitabilityOverviewCards`, `BrandProfitabilityTable`, and any future
 * brief-level profitability UI, so the "never show a bare 0/blank" rule is
 * enforced in exactly one place. Returns `null` only when a real number is
 * safe to render (cost data visible AND no missing-reason signal). */
export function costMissingInfo(input: CostVisibilityInput): CostMissingInfo | null {
  if (!input.costDataVisible) {
    return { label: "Maliyet Verisi Gizli", hidden: true };
  }
  if (input.marginMissingReason) {
    return {
      label: MARGIN_MISSING_REASON_LABEL[input.marginMissingReason] ?? "Maliyet verisi eksik",
      hidden: false,
    };
  }
  if (input.costRateMissing) {
    return { label: MARGIN_MISSING_REASON_LABEL.cost_rate_eksik, hidden: false };
  }
  return null;
}

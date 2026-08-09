"use client";

import { BrandProfitabilityTable, type BrandProfitabilityRow } from "@/components/finance/BrandProfitabilityTable";
import { ProfitabilityOverviewCards } from "@/components/finance/ProfitabilityOverviewCards";
import {
  computePresetRange,
  ProfitabilityPeriodFilter,
  type ProfitabilityPeriodValue,
} from "@/components/finance/ProfitabilityPeriodFilter";
import { ProfitabilityRiskPanel } from "@/components/finance/ProfitabilityRiskPanel";
import { useWorkspace } from "@/context/workspace-context";
import { useAuth } from "@/hooks/useAuth";
import {
  agencyApi,
  ApiError,
  financeApi,
  type AgencyProfitabilityOverview,
  type BrandRead,
  type ProfitabilityRiskFlag,
} from "@/lib/api-client";
import { X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.detail === "string") return e.detail;
    return e.message;
  }
  return e instanceof Error ? e.message : "Yüklenemedi";
}

/** Agency-wide profitability dashboard — Phase 6 of the resource/finance
 * plan (plan §11/§14), the final feature phase before the RBAC/audit sweep
 * and e2e tests. Reads `GET /finance/profitability/overview` and fans out
 * `GET /finance/profitability/brand/{id}` per brand (same bounded N+1
 * pattern already used by `RetainersPage`/`FinanceSettingsPage` — there is
 * no bulk per-brand profitability endpoint). No role gate of its own: the
 * "Kârlılık" nav item is `ownerOnly` (matches how "Faturalar" was handled
 * in Phase 4), but the backend's `PROFITABILITY_VIEW` permission is the
 * real gate and also covers Admin/Brand Manager per plan §8 — a direct URL
 * visit from either role works exactly like this page working for anyone
 * with `INVOICE_VIEW` on the invoices page. */
export default function ProfitabilityPage() {
  const { accessToken } = useAuth();
  const { activeAgency, isInitialized } = useWorkspace();
  const agencyId = activeAgency?.id ?? null;

  const [period, setPeriod] = useState<ProfitabilityPeriodValue>(() => ({
    preset: "monthly",
    ...computePresetRange("monthly"),
  }));

  const [brands, setBrands] = useState<BrandRead[]>([]);

  const [overview, setOverview] = useState<AgencyProfitabilityOverview | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [overviewError, setOverviewError] = useState<string | null>(null);

  const [brandRows, setBrandRows] = useState<BrandProfitabilityRow[]>([]);
  const [brandRowsLoading, setBrandRowsLoading] = useState(true);
  const [brandRowsError, setBrandRowsError] = useState<string | null>(null);

  const [brandFilter, setBrandFilter] = useState<string | null>(null);
  const brandSectionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!accessToken || !agencyId) return;
    agencyApi
      .listBrands(agencyId, accessToken)
      .then(setBrands)
      .catch(() => {
        /* non-fatal: brand names fall back to raw ids in risk chips */
      });
  }, [accessToken, agencyId]);

  const brandNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const b of brands) map[b.id] = b.name;
    return map;
  }, [brands]);

  const loadOverview = useCallback(async () => {
    if (!accessToken || !agencyId) return;
    setOverviewLoading(true);
    setOverviewError(null);
    try {
      const data = await financeApi.getProfitabilityOverview(agencyId, accessToken, {
        start: period.start,
        end: period.end,
      });
      setOverview(data);
    } catch (e) {
      setOverviewError(errorMessage(e));
    } finally {
      setOverviewLoading(false);
    }
  }, [accessToken, agencyId, period.start, period.end]);

  useEffect(() => {
    loadOverview();
  }, [loadOverview]);

  // Per-brand fan-out (bounded by agency roster size) — same pattern as
  // RetainersPage. A per-brand failure is surfaced as a count, never
  // silently dropped, and never blocks the other brands' rows from
  // rendering.
  const loadBrandRows = useCallback(async () => {
    if (!accessToken || !agencyId) return;
    if (brands.length === 0) {
      setBrandRows([]);
      setBrandRowsLoading(false);
      return;
    }
    setBrandRowsLoading(true);
    setBrandRowsError(null);
    try {
      const results = await Promise.all(
        brands.map(async (b) => {
          try {
            const data = await financeApi.getBrandProfitability(b.id, agencyId, accessToken, {
              start: period.start,
              end: period.end,
            });
            return { brand: b, data, failed: false };
          } catch {
            return { brand: b, data: null, failed: true };
          }
        })
      );

      const rows: BrandProfitabilityRow[] = [];
      for (const r of results) {
        if (!r.data) continue;
        const riskCount = r.data.risk_flags.length;
        for (const cf of r.data.currencies) {
          rows.push({
            brandId: r.brand.id,
            brandName: r.brand.name,
            currency: cf.currency,
            invoicedRevenueCents: cf.invoiced_revenue_cents,
            unbilledWipCents: cf.unbilled_wip_cents,
            unbilledWipHours: cf.unbilled_wip_hours,
            billingRateMissingForWip: cf.billing_rate_missing_for_wip,
            internalCostCents: cf.internal_cost_cents,
            grossProfitCents: cf.gross_profit_cents,
            grossMarginPct: cf.gross_margin_pct,
            costDataVisible: cf.cost_data_visible,
            marginMissingReason: cf.margin_missing_reason,
            retainer: r.data.retainer,
            riskCount,
          });
        }
      }
      rows.sort((a, b) => a.brandName.localeCompare(b.brandName, "tr") || a.currency.localeCompare(b.currency));
      setBrandRows(rows);

      const failedCount = results.filter((r) => r.failed).length;
      setBrandRowsError(
        failedCount > 0 ? `${failedCount} marka için kârlılık verisi yüklenemedi.` : null
      );
    } finally {
      setBrandRowsLoading(false);
    }
  }, [accessToken, agencyId, brands, period.start, period.end]);

  useEffect(() => {
    loadBrandRows();
  }, [loadBrandRows]);

  const handleRiskSelect = (flag: ProfitabilityRiskFlag) => {
    if (flag.brand_id) setBrandFilter(flag.brand_id);
    brandSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const visibleBrandRows = brandFilter
    ? brandRows.filter((r) => r.brandId === brandFilter)
    : brandRows;

  if (!isInitialized || !agencyId || !accessToken) return null;

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-text">Kârlılık</h1>
        <p className="text-sm text-text-muted mt-1">
          Ajans genelinde ve marka bazında gerçekleşen gelir, iç maliyet ve brüt kâr marjı — para
          birimleri asla birleştirilmez, her para birimi kendi başlığı altında gösterilir.
        </p>
      </div>

      <ProfitabilityPeriodFilter value={period} onChange={setPeriod} />

      <section>
        <h2 className="text-sm font-semibold text-text mb-3">Genel Bakış</h2>
        {overviewError ? (
          <div className="bg-danger/10 border border-danger/30 rounded-xl p-4 text-sm text-danger">
            {overviewError}
          </div>
        ) : (
          <ProfitabilityOverviewCards overview={overview} loading={overviewLoading} />
        )}
      </section>

      {overview && overview.risk_flags.length > 0 && (
        <ProfitabilityRiskPanel
          riskFlags={overview.risk_flags}
          brandNames={brandNames}
          onSelect={handleRiskSelect}
        />
      )}

      <section ref={brandSectionRef}>
        <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
          <h2 className="text-sm font-semibold text-text">Marka Bazlı</h2>
          {brandFilter && (
            <button
              type="button"
              onClick={() => setBrandFilter(null)}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-text-muted hover:text-text transition-colors"
            >
              <X className="w-3.5 h-3.5" />
              Filtreyi Temizle ({brandNames[brandFilter] ?? "1 marka"})
            </button>
          )}
        </div>
        <BrandProfitabilityTable rows={visibleBrandRows} loading={brandRowsLoading} error={brandRowsError} />
      </section>
    </div>
  );
}

import { MissingRateLabel } from "@/components/finance/MissingRateLabel";
import { DataTable, type DataTableColumn } from "@/components/ui/data-table";
import { Skeleton } from "@/components/ui/skeleton";
import type { MarginMissingReasonValue, ProfitabilityRetainerUtilization } from "@/lib/api-client";
import { costMissingInfo, formatMoneyCents, formatPct } from "@/lib/finance";
import { AlertTriangle, Building2 } from "lucide-react";

export interface BrandProfitabilityRow {
  brandId: string;
  brandName: string;
  currency: string;
  invoicedRevenueCents: number;
  unbilledWipCents: number | null;
  unbilledWipHours: number;
  billingRateMissingForWip: boolean;
  internalCostCents: number | null;
  grossProfitCents: number | null;
  grossMarginPct: number | null;
  costDataVisible: boolean;
  marginMissingReason: MarginMissingReasonValue | null;
  retainer: ProfitabilityRetainerUtilization | null;
  riskCount: number;
}

interface BrandProfitabilityTableProps {
  rows: BrandProfitabilityRow[];
  loading: boolean;
  error: string | null;
}

/** Per-(brand, currency) profitability breakdown — a brand with commercial
 * terms in more than one currency gets one row per currency, never a
 * blended total across them (plan §7/§13). Cost/margin/WIP-pricing cells
 * render `MissingRateLabel` instead of a number whenever the underlying
 * rate is missing or hidden — see `lib/finance.ts`'s `costMissingInfo`. */
export function BrandProfitabilityTable({ rows, loading, error }: BrandProfitabilityTableProps) {
  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-14 w-full rounded-xl" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-warning/10 border border-warning/30 rounded-xl p-4 text-sm text-warning flex items-center gap-2">
        <AlertTriangle className="w-4 h-4 flex-shrink-0" />
        {error}
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center border border-dashed border-border rounded-xl">
        <div className="w-14 h-14 bg-surface-2 rounded-2xl flex items-center justify-center mb-4">
          <Building2 className="w-6 h-6 text-text-muted" />
        </div>
        <p className="text-sm font-medium text-text mb-1">Görüntülenecek marka verisi yok</p>
        <p className="text-xs text-text-muted max-w-sm">
          Seçili dönem ve filtre için hiçbir markanın kârlılık verisi bulunamadı.
        </p>
      </div>
    );
  }

  const columns: DataTableColumn<BrandProfitabilityRow>[] = [
    {
      key: "brand",
      header: "Marka",
      render: (r) => (
        <div className="min-w-0">
          <p className="text-sm font-medium text-text truncate">{r.brandName}</p>
          <span className="text-[11px] text-text-muted">{r.currency}</span>
        </div>
      ),
      sortValue: (r) => r.brandName,
    },
    {
      key: "revenue",
      header: "Faturalanmış Gelir",
      render: (r) => formatMoneyCents(r.invoicedRevenueCents, r.currency),
      sortValue: (r) => r.invoicedRevenueCents,
      align: "right",
    },
    {
      key: "wip",
      header: "Faturalanmamış WIP",
      render: (r) =>
        r.billingRateMissingForWip ? (
          <MissingRateLabel text="Fiyatlandırma eksik" hidden={false} />
        ) : (
          <div className="text-right">
            <p className="tabular-nums">{formatMoneyCents(r.unbilledWipCents, r.currency)}</p>
            <p className="text-[11px] text-text-muted tabular-nums">{r.unbilledWipHours} saat</p>
          </div>
        ),
      sortValue: (r) => r.unbilledWipHours,
      align: "right",
    },
    {
      key: "cost",
      header: "İç Maliyet",
      render: (r) => {
        const info = costMissingInfo({
          costDataVisible: r.costDataVisible,
          marginMissingReason: r.marginMissingReason,
        });
        return info ? (
          <MissingRateLabel text={info.label} hidden={info.hidden} />
        ) : (
          formatMoneyCents(r.internalCostCents, r.currency)
        );
      },
      align: "right",
    },
    {
      key: "profit",
      header: "Brüt Kâr",
      render: (r) => {
        const info = costMissingInfo({
          costDataVisible: r.costDataVisible,
          marginMissingReason: r.marginMissingReason,
        });
        return info ? (
          <MissingRateLabel text={info.label} hidden={info.hidden} />
        ) : (
          formatMoneyCents(r.grossProfitCents, r.currency)
        );
      },
      sortValue: (r) => r.grossProfitCents ?? Number.NEGATIVE_INFINITY,
      align: "right",
    },
    {
      key: "margin",
      header: "Marj",
      render: (r) => {
        const info = costMissingInfo({
          costDataVisible: r.costDataVisible,
          marginMissingReason: r.marginMissingReason,
        });
        if (info) return <MissingRateLabel text={info.label} hidden={info.hidden} />;
        const pct = r.grossMarginPct;
        const color = pct === null || pct === undefined ? "" : pct < 0 ? "text-danger" : pct < 20 ? "text-warning" : "text-success";
        return <span className={`tabular-nums font-medium ${color}`}>{formatPct(pct)}</span>;
      },
      sortValue: (r) => r.grossMarginPct ?? Number.NEGATIVE_INFINITY,
      align: "right",
    },
    {
      key: "retainer",
      header: "Retainer Kullanımı",
      render: (r) =>
        r.retainer ? (
          <div className="text-right">
            <p className="tabular-nums">
              {Math.round(r.retainer.used_minutes / 60)}s / {Math.round(r.retainer.included_minutes / 60)}s
            </p>
            {r.retainer.overage_minutes > 0 && (
              <p className="text-[11px] text-danger tabular-nums">
                +{Math.round(r.retainer.overage_minutes / 60)}s aşım
              </p>
            )}
          </div>
        ) : (
          <span className="text-text-muted">—</span>
        ),
      align: "right",
    },
    {
      key: "risk",
      header: "Risk",
      render: (r) =>
        r.riskCount > 0 ? (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-warning">
            <AlertTriangle className="w-3.5 h-3.5" />
            {r.riskCount}
          </span>
        ) : (
          <span className="text-text-muted">—</span>
        ),
      align: "center",
    },
  ];

  return (
    <>
      <div className="hidden md:block">
        <DataTable
          columns={columns}
          data={rows}
          rowKey={(r) => `${r.brandId}-${r.currency}`}
          emptyMessage="Görüntülenecek marka verisi yok"
        />
      </div>

      {/* Mobile: brand cards — an 8-column table doesn't fit 390px, per the
          responsiveness contract documented on DataTable. */}
      <div className="md:hidden flex flex-col gap-3">
        {rows.map((r) => {
          const missing = costMissingInfo({
            costDataVisible: r.costDataVisible,
            marginMissingReason: r.marginMissingReason,
          });
          const pct = r.grossMarginPct;
          const marginColor =
            pct === null || pct === undefined ? "" : pct < 0 ? "text-danger" : pct < 20 ? "text-warning" : "text-success";
          return (
            <div key={`${r.brandId}-${r.currency}`} className="bg-surface border border-border rounded-xl p-4">
              <div className="flex items-center justify-between gap-2 mb-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-text truncate">{r.brandName}</p>
                  <span className="text-[11px] text-text-muted">{r.currency}</span>
                </div>
                {r.riskCount > 0 && (
                  <span className="flex-shrink-0 inline-flex items-center gap-1 text-xs font-medium text-warning">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    {r.riskCount}
                  </span>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-surface-2 rounded-lg p-2.5">
                  <p className="text-[10px] text-text-muted mb-0.5">Gelir</p>
                  <p className="text-sm font-semibold text-text tabular-nums">
                    {formatMoneyCents(r.invoicedRevenueCents, r.currency)}
                  </p>
                </div>
                <div className="bg-surface-2 rounded-lg p-2.5">
                  <p className="text-[10px] text-text-muted mb-0.5">Maliyet</p>
                  {missing ? (
                    <MissingRateLabel text={missing.label} hidden={missing.hidden} />
                  ) : (
                    <p className="text-sm font-semibold text-text tabular-nums">
                      {formatMoneyCents(r.internalCostCents, r.currency)}
                    </p>
                  )}
                </div>
                <div className="bg-surface-2 rounded-lg p-2.5">
                  <p className="text-[10px] text-text-muted mb-0.5">Brüt Kâr</p>
                  {missing ? (
                    <MissingRateLabel text={missing.label} hidden={missing.hidden} />
                  ) : (
                    <p className="text-sm font-semibold text-text tabular-nums">
                      {formatMoneyCents(r.grossProfitCents, r.currency)}
                    </p>
                  )}
                </div>
                <div className="bg-surface-2 rounded-lg p-2.5">
                  <p className="text-[10px] text-text-muted mb-0.5">Marj</p>
                  {missing ? (
                    <MissingRateLabel text={missing.label} hidden={missing.hidden} />
                  ) : (
                    <p className={`text-sm font-semibold tabular-nums ${marginColor}`}>{formatPct(pct)}</p>
                  )}
                </div>
              </div>
              {r.billingRateMissingForWip && (
                <div className="mt-3">
                  <MissingRateLabel text="Fiyatlandırma eksik" hidden={false} />
                </div>
              )}
              {r.retainer && (
                <p className="mt-3 text-xs text-text-muted">
                  Retainer: {Math.round(r.retainer.used_minutes / 60)}s / {Math.round(r.retainer.included_minutes / 60)}s
                  {r.retainer.overage_minutes > 0 && (
                    <span className="text-danger"> (+{Math.round(r.retainer.overage_minutes / 60)}s aşım)</span>
                  )}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}

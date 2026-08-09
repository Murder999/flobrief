import { MissingRateLabel } from "@/components/finance/MissingRateLabel";
import { StatCard } from "@/components/ui/stat-card";
import type { AgencyCurrencyOverview, AgencyProfitabilityOverview } from "@/lib/api-client";
import { costMissingInfo, formatMoneyCents, formatPct } from "@/lib/finance";
import { Coins, PiggyBank, Receipt, TrendingDown, TrendingUp, Wallet } from "lucide-react";

interface ProfitabilityOverviewCardsProps {
  overview: AgencyProfitabilityOverview | null;
  loading: boolean;
}

function CurrencyGroup({ cf }: { cf: AgencyCurrencyOverview }) {
  const costInfo = costMissingInfo({
    costDataVisible: cf.cost_data_visible,
    costRateMissing: cf.cost_rate_missing,
  });

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs font-semibold text-text-muted tracking-wide uppercase">
          {cf.currency}
        </span>
        <div className="h-px flex-1 bg-border" />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard
          label="Faturalanmış Gelir"
          value={formatMoneyCents(cf.invoiced_revenue_cents, cf.currency)}
          icon={<Receipt className="w-4 h-4" />}
        />
        <StatCard
          label="Faturalanmamış WIP"
          value={formatMoneyCents(cf.unbilled_wip_cents, cf.currency)}
          icon={<Wallet className="w-4 h-4" />}
        />
        <StatCard
          label="İç Maliyet"
          value={
            costInfo ? (
              <MissingRateLabel text={costInfo.label} hidden={costInfo.hidden} />
            ) : (
              formatMoneyCents(cf.internal_cost_cents, cf.currency)
            )
          }
          icon={<Coins className="w-4 h-4" />}
        />
        <StatCard
          label="Brüt Kâr"
          value={
            costInfo ? (
              <MissingRateLabel text={costInfo.label} hidden={costInfo.hidden} />
            ) : (
              formatMoneyCents(cf.gross_profit_cents, cf.currency)
            )
          }
          icon={
            costInfo ? (
              <Coins className="w-4 h-4" />
            ) : (cf.gross_profit_cents ?? 0) >= 0 ? (
              <TrendingUp className="w-4 h-4" />
            ) : (
              <TrendingDown className="w-4 h-4" />
            )
          }
        />
        <StatCard
          label="Ortalama Marj"
          value={
            costInfo ? (
              <MissingRateLabel text={costInfo.label} hidden={costInfo.hidden} />
            ) : (
              formatPct(cf.average_margin_pct)
            )
          }
          icon={<PiggyBank className="w-4 h-4" />}
        />
        <StatCard
          label="Gecikmiş Alacak"
          value={formatMoneyCents(cf.overdue_receivables_cents, cf.currency)}
          icon={<Receipt className="w-4 h-4" />}
          className={cf.overdue_receivables_cents > 0 ? "border-danger/30" : undefined}
        />
      </div>
    </div>
  );
}

/** Agency-wide profitability overview, grouped and labeled by currency —
 * brands billing in different currencies are NEVER summed into one blended
 * total (plan §7/§13's multi-currency rule); each currency gets its own
 * header and its own row of stat cards. Cost/margin cells render an
 * explicit `MissingRateLabel` (never a bare 0/blank) whenever
 * `cost_data_visible` is false (viewer lacks COST_RATE_VIEW) or
 * `cost_rate_missing` is true (no cost rate configured for some
 * contributor) — see `lib/finance.ts`'s `costMissingInfo`. */
export function ProfitabilityOverviewCards({ overview, loading }: ProfitabilityOverviewCardsProps) {
  if (loading) {
    return (
      <div className="space-y-6">
        {[0, 1].map((i) => (
          <div key={i} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 3 }).map((_, j) => (
              <StatCard key={j} label="" value="" loading />
            ))}
          </div>
        ))}
      </div>
    );
  }

  if (!overview || overview.currencies.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center border border-dashed border-border rounded-xl">
        <div className="w-14 h-14 bg-surface-2 rounded-2xl flex items-center justify-center mb-4">
          <Coins className="w-6 h-6 text-text-muted" />
        </div>
        <p className="text-sm font-medium text-text mb-1">Bu dönem için henüz veri yok</p>
        <p className="text-xs text-text-muted max-w-sm">
          Seçili dönemde faturalanmış gelir veya faturalanmamış billable iş bulunamadı.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {overview.currencies.map((cf) => (
        <CurrencyGroup key={cf.currency} cf={cf} />
      ))}
    </div>
  );
}

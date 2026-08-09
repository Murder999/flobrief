import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { RetainerSummary } from "@/lib/api-client";
import { formatMinutesAsHours } from "@/lib/capacity";
import { formatDate, formatMoneyCents } from "@/lib/finance";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface RetainerSummaryCardProps {
  brandName: string;
  summary: RetainerSummary;
}

/** Per-brand retainer consumption for the current period — included/used/
 * remaining/overage minutes, period dates, rollover indicator. Overage is
 * never silently hidden: when `overage_minutes > 0` a warning row with the
 * extra cost renders, never color-only (icon + text, matches the
 * capacity/invoice status badge convention). */
export function RetainerSummaryCard({ brandName, summary }: RetainerSummaryCardProps) {
  const totalAvailable = summary.included_minutes + summary.rolled_over_minutes;
  const usedPct = totalAvailable > 0 ? Math.min(100, Math.round((summary.used_minutes / totalAvailable) * 100)) : 0;
  const hasOverage = summary.overage_minutes > 0;

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{brandName}</CardTitle>
          <p className="text-xs text-text-muted mt-1">
            {formatDate(summary.period_start)} – {formatDate(summary.period_end)}
          </p>
        </div>
        {summary.rolled_over_minutes > 0 && (
          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-info flex-shrink-0">
            <RefreshCw className="w-3.5 h-3.5" />
            {formatMinutesAsHours(summary.rolled_over_minutes)} devir
          </span>
        )}
      </CardHeader>
      <CardContent>
        <div className="mb-4">
          <div className="h-2 rounded-full bg-surface-2 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${hasOverage ? "bg-danger" : usedPct >= 85 ? "bg-warning" : "bg-accent"}`}
              style={{ width: `${usedPct}%` }}
            />
          </div>
          <p className="text-xs text-text-muted mt-1.5">%{usedPct} kullanıldı</p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
          <div>
            <p className="text-xs text-text-muted">Dahil Süre</p>
            <p className="font-medium text-text tabular-nums">{formatMinutesAsHours(summary.included_minutes)}</p>
          </div>
          <div>
            <p className="text-xs text-text-muted">Kullanılan</p>
            <p className="font-medium text-text tabular-nums">{formatMinutesAsHours(summary.used_minutes)}</p>
          </div>
          <div>
            <p className="text-xs text-text-muted">Kalan</p>
            <p className="font-medium text-text tabular-nums">{formatMinutesAsHours(summary.remaining_minutes)}</p>
          </div>
          <div>
            <p className="text-xs text-text-muted">Aşım</p>
            <p className={`font-medium tabular-nums ${hasOverage ? "text-danger" : "text-text"}`}>
              {formatMinutesAsHours(summary.overage_minutes)}
            </p>
          </div>
        </div>

        {hasOverage && (
          <div className="mt-4 flex items-center gap-2 px-3 py-2 rounded-lg bg-danger/10 border border-danger/20 text-xs text-danger">
            <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
            <span>
              {formatMinutesAsHours(summary.overage_minutes)} aşım —{" "}
              {formatMoneyCents(summary.overage_cost_cents, summary.currency)} ek maliyet
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

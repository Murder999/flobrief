import type { CategoryBreakdown } from "@/lib/api-client";
import { TIME_CATEGORY_LABEL } from "./TimeCategoryBadge";

interface TimeBarChartProps {
  data: CategoryBreakdown[];
  emptyLabel?: string;
}

/** Hand-rolled CSS-width-percentage bars — no charting library, matching
 * this codebase's `/dashboard/reports` convention of zero interactive charts. */
export function TimeBarChart({ data, emptyLabel = "Bu aralıkta zaman kaydı yok" }: TimeBarChartProps) {
  if (data.length === 0) {
    return <p className="text-xs text-text-muted py-4 text-center">{emptyLabel}</p>;
  }

  const maxHours = Math.max(...data.map((d) => d.hours), 0.01);

  return (
    <div className="flex flex-col gap-2.5">
      {data.map((row) => {
        const pct = Math.max(2, Math.round((row.hours / maxHours) * 100));
        return (
          <div key={row.category} className="flex items-center gap-3">
            <span className="w-28 flex-shrink-0 text-xs text-text-secondary truncate">
              {TIME_CATEGORY_LABEL[row.category] ?? row.category}
            </span>
            <div className="flex-1 h-2 rounded-full bg-surface-2 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-accent transition-all duration-300"
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="w-16 flex-shrink-0 text-right text-xs font-medium text-text tabular-nums">
              {row.hours.toFixed(1)}s
            </span>
          </div>
        );
      })}
    </div>
  );
}

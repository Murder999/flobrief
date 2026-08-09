"use client";

import { cn } from "@/lib/utils";
import { useState } from "react";

export type ProfitabilityPeriodPreset = "weekly" | "monthly" | "quarterly" | "custom";

export interface ProfitabilityPeriodValue {
  preset: ProfitabilityPeriodPreset;
  start: string;
  end: string;
}

const PRESET_LABELS: { value: Exclude<ProfitabilityPeriodPreset, "custom">; label: string }[] = [
  { value: "weekly", label: "Haftalık" },
  { value: "monthly", label: "Aylık" },
  { value: "quarterly", label: "Çeyreklik" },
];

// Local calendar date, not toISOString() — toISOString() converts to UTC
// first, which silently shifts the date across midnight for any user west
// of UTC (same reasoning as hooks/useDateRangeFilter.ts's localISODate).
function localISODate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function computePresetRange(
  preset: Exclude<ProfitabilityPeriodPreset, "custom">
): { start: string; end: string } {
  const now = new Date();
  if (preset === "weekly") {
    const day = now.getDay(); // 0 = Sunday .. 6 = Saturday
    const diffToMonday = day === 0 ? -6 : 1 - day;
    const monday = new Date(now.getFullYear(), now.getMonth(), now.getDate() + diffToMonday);
    const sunday = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + 6);
    return { start: localISODate(monday), end: localISODate(sunday) };
  }
  if (preset === "monthly") {
    const start = new Date(now.getFullYear(), now.getMonth(), 1);
    const end = new Date(now.getFullYear(), now.getMonth() + 1, 0);
    return { start: localISODate(start), end: localISODate(end) };
  }
  // quarterly
  const quarterStartMonth = Math.floor(now.getMonth() / 3) * 3;
  const start = new Date(now.getFullYear(), quarterStartMonth, 1);
  const end = new Date(now.getFullYear(), quarterStartMonth + 3, 0);
  return { start: localISODate(start), end: localISODate(end) };
}

interface ProfitabilityPeriodFilterProps {
  value: ProfitabilityPeriodValue;
  onChange: (value: ProfitabilityPeriodValue) => void;
}

/** Weekly/monthly/quarterly/custom period selector for the profitability
 * dashboard (plan §11's "Dönem seçimi"). `hooks/useDateRangeFilter` (used by
 * the team time-report pages) only offers last7/this_month/last_month/
 * custom and is URL-persisted for a different page family — rather than
 * widen that shared hook's contract for one page, this is a small
 * self-contained component matching its exact pill-button visual style. */
export function ProfitabilityPeriodFilter({ value, onChange }: ProfitabilityPeriodFilterProps) {
  const [customStart, setCustomStart] = useState(value.start);
  const [customEnd, setCustomEnd] = useState(value.end);
  const [rangeError, setRangeError] = useState<string | null>(null);

  const applyCustom = (start: string, end: string) => {
    if (!start || !end) return;
    if (start > end) {
      setRangeError("Başlangıç tarihi bitiş tarihinden sonra olamaz.");
      return;
    }
    setRangeError(null);
    onChange({ preset: "custom", start, end });
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-1.5">
        {PRESET_LABELS.map((p) => (
          <button
            key={p.value}
            type="button"
            onClick={() => onChange({ preset: p.value, ...computePresetRange(p.value) })}
            className={cn(
              "px-2.5 py-1.5 rounded-lg text-[12px] font-medium border transition-colors",
              value.preset === p.value
                ? "bg-accent text-white border-accent"
                : "bg-surface text-text-muted border-border hover:border-accent/40"
            )}
          >
            {p.label}
          </button>
        ))}

        <div className="flex items-center gap-1.5">
          <input
            type="date"
            value={customStart}
            onChange={(e) => {
              setCustomStart(e.target.value);
              applyCustom(e.target.value, customEnd);
            }}
            className={cn(
              "h-8 px-2 rounded-lg text-[12px] bg-surface border text-text focus:outline-none focus:border-accent/60",
              value.preset === "custom" ? "border-accent/60" : "border-border"
            )}
            aria-label="Başlangıç tarihi"
          />
          <span className="text-text-muted text-xs">–</span>
          <input
            type="date"
            value={customEnd}
            onChange={(e) => {
              setCustomEnd(e.target.value);
              applyCustom(customStart, e.target.value);
            }}
            className={cn(
              "h-8 px-2 rounded-lg text-[12px] bg-surface border text-text focus:outline-none focus:border-accent/60",
              value.preset === "custom" ? "border-accent/60" : "border-border"
            )}
            aria-label="Bitiş tarihi"
          />
        </div>
      </div>
      {rangeError && <p className="text-[11px] text-danger">{rangeError}</p>}
    </div>
  );
}

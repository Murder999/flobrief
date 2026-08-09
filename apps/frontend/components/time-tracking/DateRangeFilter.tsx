"use client";

import { cn } from "@/lib/utils";
import type { DateRangePreset, DateRangeValue } from "@/hooks/useDateRangeFilter";
import { X } from "lucide-react";
import { useState } from "react";

const PRESET_LABELS: { value: Exclude<DateRangePreset, "custom">; label: string }[] = [
  { value: "last7", label: "Son 7 Gün" },
  { value: "this_month", label: "Bu Ay" },
  { value: "last_month", label: "Geçen Ay" },
];

interface DateRangeFilterProps {
  value: DateRangeValue;
  onPresetChange: (preset: Exclude<DateRangePreset, "custom">) => void;
  onCustomChange: (start: string, end: string) => void;
  onClear: () => void;
}

export function DateRangeFilter({
  value,
  onPresetChange,
  onCustomChange,
  onClear,
}: DateRangeFilterProps) {
  const [customStart, setCustomStart] = useState(value.start ?? "");
  const [customEnd, setCustomEnd] = useState(value.end ?? "");
  const [rangeError, setRangeError] = useState<string | null>(null);

  const applyCustom = (start: string, end: string) => {
    if (!start || !end) return;
    if (start > end) {
      setRangeError("Başlangıç tarihi bitiş tarihinden sonra olamaz.");
      return;
    }
    setRangeError(null);
    onCustomChange(start, end);
  };

  return (
    <div className="flex flex-col gap-2 mb-5">
      <div className="flex flex-wrap items-center gap-1.5">
        {PRESET_LABELS.map((p) => (
          <button
            key={p.value}
            type="button"
            onClick={() => onPresetChange(p.value)}
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
              applyCustom(e.target.value, customEnd || value.end || "");
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
              applyCustom(customStart || value.start || "", e.target.value);
            }}
            className={cn(
              "h-8 px-2 rounded-lg text-[12px] bg-surface border text-text focus:outline-none focus:border-accent/60",
              value.preset === "custom" ? "border-accent/60" : "border-border"
            )}
            aria-label="Bitiş tarihi"
          />
        </div>

        {(value.preset || value.start || value.end) && (
          <button
            type="button"
            onClick={() => {
              setCustomStart("");
              setCustomEnd("");
              setRangeError(null);
              onClear();
            }}
            className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-[12px] font-medium text-text-muted hover:text-text hover:bg-hover transition-colors"
          >
            <X className="w-3 h-3" />
            Filtreyi Temizle
          </button>
        )}
      </div>
      {rangeError && <p className="text-[11px] text-danger">{rangeError}</p>}
    </div>
  );
}

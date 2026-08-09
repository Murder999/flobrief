import type { TimeEntryRead } from "@/lib/api-client";
import { TIME_CATEGORY_LABEL } from "./TimeCategoryBadge";

interface WeeklyTimesheetGridProps {
  /** Monday of the displayed week. */
  weekStart: Date;
  byDay: Record<string, number>;
  entries: TimeEntryRead[];
}

const DAY_LABELS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];

function toIsoDate(d: Date): string {
  // Native Date math only, no date library — matches this codebase's
  // toLocaleDateString("tr-TR")-only convention.
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Mon–Sun grid computed entirely from native Date arithmetic. */
export function WeeklyTimesheetGrid({ weekStart, byDay, entries }: WeeklyTimesheetGridProps) {
  const days = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(weekStart);
    d.setDate(weekStart.getDate() + i);
    return d;
  });

  const maxHours = Math.max(...days.map((d) => byDay[toIsoDate(d)] ?? 0), 1);
  const today = toIsoDate(new Date());

  const entriesByDay = entries.reduce<Record<string, TimeEntryRead[]>>((acc, e) => {
    const key = e.started_at.slice(0, 10);
    (acc[key] ??= []).push(e);
    return acc;
  }, {});

  return (
    <>
      {/* Desktop/tablet: 7-column bar-chart grid. */}
      <div className="hidden sm:grid sm:grid-cols-7 gap-2">
        {days.map((d, i) => {
          const iso = toIsoDate(d);
          const hours = byDay[iso] ?? 0;
          const heightPct = hours > 0 ? Math.max(8, Math.round((hours / maxHours) * 100)) : 0;
          const dayEntries = entriesByDay[iso] ?? [];
          const isToday = iso === today;

          return (
            <div
              key={iso}
              className={`flex flex-col rounded-xl border p-2.5 min-h-[160px] ${
                isToday ? "border-accent/40 bg-accent-subtle/30" : "border-border bg-surface"
              }`}
            >
              <div className="flex items-baseline justify-between mb-2">
                <span className="text-[11px] font-semibold text-text-muted tracking-wide">
                  {DAY_LABELS[i]}
                </span>
                <span className="text-[11px] text-text-muted">{d.getDate()}</span>
              </div>

              <div className="flex-1 flex items-end mb-2">
                <div className="w-full h-16 flex items-end">
                  <div
                    className="w-full rounded-md bg-gradient-accent transition-all duration-300"
                    style={{ height: `${heightPct}%`, minHeight: hours > 0 ? "6px" : "0" }}
                  />
                </div>
              </div>

              <p className="text-sm font-semibold text-text tabular-nums mb-1">
                {hours > 0 ? `${hours.toFixed(1)}s` : "—"}
              </p>

              <div className="flex flex-col gap-1">
                {dayEntries.slice(0, 3).map((e) => (
                  <p key={e.id} className="text-[10px] text-text-muted truncate">
                    {TIME_CATEGORY_LABEL[e.category] ?? e.category}
                  </p>
                ))}
                {dayEntries.length > 3 && (
                  <p className="text-[10px] text-text-muted/70">+{dayEntries.length - 3} daha</p>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Mobile: stacked daily accordion cards — a 7-column grid does not fit 390px. */}
      <div className="flex flex-col gap-2 sm:hidden">
        {days.map((d, i) => {
          const iso = toIsoDate(d);
          const hours = byDay[iso] ?? 0;
          const barPct = hours > 0 ? Math.max(8, Math.round((hours / maxHours) * 100)) : 0;
          const dayEntries = entriesByDay[iso] ?? [];
          const isToday = iso === today;

          return (
            <details
              key={iso}
              open={isToday}
              className={`rounded-xl border ${
                isToday ? "border-accent/40 bg-accent-subtle/30" : "border-border bg-surface"
              }`}
            >
              <summary className="flex items-center gap-3 p-3 cursor-pointer list-none [&::-webkit-details-marker]:hidden min-h-[44px]">
                <div className="w-11 text-center flex-shrink-0">
                  <p className="text-[11px] font-semibold text-text-muted tracking-wide">{DAY_LABELS[i]}</p>
                  <p className="text-[11px] text-text-muted">{d.getDate()}</p>
                </div>
                <div className="flex-1 h-2 rounded-full bg-surface-2 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-gradient-accent transition-all duration-300"
                    style={{ width: `${barPct}%` }}
                  />
                </div>
                <p className="text-sm font-semibold text-text tabular-nums flex-shrink-0 w-14 text-right">
                  {hours > 0 ? `${hours.toFixed(1)}s` : "—"}
                </p>
              </summary>
              {dayEntries.length > 0 && (
                <div className="px-3 pb-3 flex flex-col gap-1 border-t border-border pt-2 ml-14">
                  {dayEntries.map((e) => (
                    <p key={e.id} className="text-xs text-text-muted truncate">
                      {TIME_CATEGORY_LABEL[e.category] ?? e.category}
                    </p>
                  ))}
                </div>
              )}
            </details>
          );
        })}
      </div>
    </>
  );
}

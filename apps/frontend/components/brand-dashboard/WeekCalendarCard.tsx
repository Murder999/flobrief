"use client";

import Link from "next/link";
import { CalendarClock } from "lucide-react";
import type { BrandCalendarEntry } from "@/lib/api-client";
import { EVENT_TYPE_CFG, STATUS_CFG } from "@/components/brand-calendar/labels";
import { cn } from "@/lib/utils";

function RowSkeleton() {
  return (
    <div className="flex items-center gap-3 px-4 py-2.5 border-b border-border last:border-0 animate-pulse">
      <div className="h-3 w-10 rounded bg-surface-2" />
      <div className="h-3.5 flex-1 rounded bg-surface-2" />
      <div className="h-4 w-16 rounded bg-surface-2" />
    </div>
  );
}

function isToday(dateStr: string): boolean {
  return dateStr === new Date().toISOString().slice(0, 10);
}

function isPast(dateStr: string): boolean {
  return dateStr < new Date().toISOString().slice(0, 10);
}

export function WeekCalendarCard({ entries }: { entries: BrandCalendarEntry[] | null }) {
  const visible = (entries ?? []).slice(0, 4);

  return (
    <div className="flex h-full flex-col rounded-xl border border-border bg-surface overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <CalendarClock className="h-4 w-4 text-accent" />
          <h2 className="text-sm font-semibold text-text">Bu Hafta</h2>
        </div>
        <Link href="/brand/calendar" className="text-xs text-accent hover:underline">
          Tümünü gör
        </Link>
      </div>

      {entries === null ? (
        <>
          <RowSkeleton />
          <RowSkeleton />
        </>
      ) : visible.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-1.5 px-4 py-6 text-center">
          <p className="text-[13px] font-medium text-text">Bu hafta planlanmış olay yok</p>
          <p className="text-[11.5px] text-text-muted">Takvim boş görünüyor.</p>
        </div>
      ) : (
        <div>
          {visible.map((entry) => {
            const evCfg = EVENT_TYPE_CFG[entry.event_type] ?? { label: entry.event_type, chip: "", dot: "bg-text-muted" };
            const stCfg = STATUS_CFG[entry.status] ?? { label: entry.status, chip: "", dot: "bg-text-muted" };
            const today = isToday(entry.entry_date);
            const overdue = isPast(entry.entry_date) && entry.status !== "published" && entry.status !== "approved" && entry.status !== "completed";
            const href = entry.brief_id ? `/brand/briefs/${entry.brief_id}` : "/brand/calendar";
            return (
              <Link
                key={entry.id}
                href={href}
                className={cn(
                  "flex items-center gap-3 px-4 py-2.5 border-b border-border last:border-0 hover:bg-surface-2 transition-colors",
                  today && "bg-accent-subtle/40"
                )}
              >
                <span className={cn("w-11 flex-shrink-0 text-[11px] font-medium", overdue ? "text-danger" : today ? "text-accent" : "text-text-muted")}>
                  {new Date(`${entry.entry_date}T00:00:00`).toLocaleDateString("tr-TR", { day: "numeric", month: "short" })}
                </span>
                <span className={cn("h-1.5 w-1.5 flex-shrink-0 rounded-full", evCfg.dot)} />
                <p className="min-w-0 flex-1 truncate text-[13px] text-text">{entry.title}</p>
                <span className={cn("flex-shrink-0 rounded-md border px-1.5 py-0.5 text-[10.5px]", stCfg.chip)}>
                  {stCfg.label}
                </span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

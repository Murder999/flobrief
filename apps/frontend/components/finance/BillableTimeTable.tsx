"use client";

import { TimeCategoryBadge } from "@/components/time-tracking/TimeCategoryBadge";
import type { BillableTimeEntryRead } from "@/lib/api-client";
import { Clock } from "lucide-react";

interface BillableTimeTableProps {
  entries: BillableTimeEntryRead[];
  loading: boolean;
  memberNames: Record<string, string>;
  briefTitles: Record<string, string>;
  selected: Set<string>;
  onToggleOne: (id: string) => void;
  onToggleAll: () => void;
  selectable: boolean;
}

function formatHours(seconds: number | null): string {
  if (!seconds) return "0.0s";
  return `${(seconds / 3600).toFixed(1)}s`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("tr-TR", { day: "numeric", month: "short", year: "numeric" });
}

function EmptyState() {
  return (
    <div className="bg-surface border border-border rounded-xl p-14 flex flex-col items-center text-center">
      <div className="w-14 h-14 bg-surface-2 rounded-2xl flex items-center justify-center mb-4">
        <Clock className="w-7 h-7 text-text-muted" />
      </div>
      <p className="text-sm font-medium text-text mb-1">Faturalandırılabilir zaman kaydı yok</p>
      <p className="text-xs text-text-muted">
        Seçilen marka ve tarih aralığında kilitlenmiş, faturalanmamış zaman kaydı bulunamadı.
      </p>
    </div>
  );
}

/** Billable/locked/un-invoiced `TimeEntry` list — desktop table with a
 * checkbox column + mobile card list, mirroring `TeamCapacityGrid`'s
 * responsive split. "Select all" only ever operates on `entries` (the
 * already brand + date-range + client-filtered list passed in), never a
 * separately-fetched full-tenant set — this is the mass-selection safety
 * property required by plan §12: there is no code path here that can select
 * rows outside what is currently rendered. */
export function BillableTimeTable({
  entries,
  loading,
  memberNames,
  briefTitles,
  selected,
  onToggleOne,
  onToggleAll,
  selectable,
}: BillableTimeTableProps) {
  if (loading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-14 bg-surface-2 rounded-xl animate-pulse" />
        ))}
      </div>
    );
  }

  if (entries.length === 0) {
    return <EmptyState />;
  }

  const allSelected = entries.length > 0 && entries.every((e) => selected.has(e.id));

  return (
    <>
      <div className="hidden md:block overflow-x-auto rounded-xl border border-border bg-surface">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface-2 border-b border-border">
              {selectable && (
                <th className="px-4 py-3 w-10">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={onToggleAll}
                    aria-label="Tümünü seç (bu listede)"
                    className="w-4 h-4 rounded border-border accent-accent cursor-pointer"
                  />
                </th>
              )}
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                Kullanıcı
              </th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                Brief
              </th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                Kategori
              </th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                Tarih
              </th>
              <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                Süre
              </th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id} className="border-b border-border last:border-0 hover:bg-hover transition-colors">
                {selectable && (
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selected.has(e.id)}
                      onChange={() => onToggleOne(e.id)}
                      aria-label="Kaydı seç"
                      className="w-4 h-4 rounded border-border accent-accent cursor-pointer"
                    />
                  </td>
                )}
                <td className="px-4 py-3 text-text">{memberNames[e.user_id] ?? "—"}</td>
                <td className="px-4 py-3 text-text-secondary truncate max-w-[220px]">
                  {e.brief_id ? briefTitles[e.brief_id] ?? "—" : "—"}
                </td>
                <td className="px-4 py-3">
                  <TimeCategoryBadge category={e.category} />
                </td>
                <td className="px-4 py-3 text-text-secondary">{formatDate(e.started_at)}</td>
                <td className="px-4 py-3 text-right text-text tabular-nums">
                  {formatHours(e.duration_seconds)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="md:hidden flex flex-col gap-3">
        {selectable && (
          <label className="flex items-center gap-2 text-xs text-text-muted px-1">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={onToggleAll}
              className="w-4 h-4 rounded border-border accent-accent cursor-pointer"
            />
            Tümünü seç (bu listede)
          </label>
        )}
        {entries.map((e) => (
          <div key={e.id} className="bg-surface border border-border rounded-xl p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-text truncate">{memberNames[e.user_id] ?? "—"}</p>
                <p className="text-xs text-text-muted truncate">
                  {e.brief_id ? briefTitles[e.brief_id] ?? "—" : "Brief yok"}
                </p>
              </div>
              {selectable && (
                <input
                  type="checkbox"
                  checked={selected.has(e.id)}
                  onChange={() => onToggleOne(e.id)}
                  aria-label="Kaydı seç"
                  className="w-4 h-4 rounded border-border accent-accent cursor-pointer flex-shrink-0 mt-1"
                />
              )}
            </div>
            <div className="mt-3 flex items-center justify-between gap-2">
              <TimeCategoryBadge category={e.category} />
              <span className="text-sm font-semibold text-text tabular-nums">
                {formatHours(e.duration_seconds)}
              </span>
            </div>
            <p className="mt-2 text-[11px] text-text-muted">{formatDate(e.started_at)}</p>
          </div>
        ))}
      </div>
    </>
  );
}

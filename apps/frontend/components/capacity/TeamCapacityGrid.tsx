"use client";

import { DataTable, type DataTableColumn } from "@/components/ui/data-table";
import { formatMinutesAsHours } from "@/lib/capacity";
import { ROLE_LABELS } from "@/lib/workspace";
import type { TeamCapacityMember } from "@/lib/api-client";
import { Timer, Users } from "lucide-react";
import Link from "next/link";
import { CapacityStatusBadge } from "./CapacityStatusBadge";

export interface TeamMemberCapacityView extends TeamCapacityMember {
  name: string;
  role: string;
  brandNames: string[];
}

interface TeamCapacityGridProps {
  rows: TeamMemberCapacityView[];
  loading: boolean;
}

function getInitials(name: string): string {
  return (
    name
      .split(" ")
      .map((w) => w[0])
      .filter(Boolean)
      .slice(0, 2)
      .join("")
      .toUpperCase() || "?"
  );
}

function MemberIdentity({ row }: { row: TeamMemberCapacityView }) {
  return (
    <Link
      href={`/dashboard/capacity/${row.user_id}`}
      className="flex items-center gap-2.5 min-w-0 group"
    >
      <div className="w-8 h-8 rounded-full bg-accent/15 flex items-center justify-center flex-shrink-0">
        <span className="text-xs font-semibold text-accent">{getInitials(row.name)}</span>
      </div>
      <div className="min-w-0">
        <p className="text-sm font-medium text-text truncate group-hover:text-accent transition-colors">
          {row.name}
        </p>
        <p className="text-[11px] text-text-muted truncate">{ROLE_LABELS[row.role] ?? row.role}</p>
      </div>
      {row.open_timer_minutes > 0 && (
        <span
          title="Açık zamanlayıcı çalışıyor"
          className="w-1.5 h-1.5 rounded-full bg-success animate-pulse flex-shrink-0"
        />
      )}
    </Link>
  );
}

function EmptyState() {
  return (
    <div className="bg-surface border border-border rounded-xl p-14 flex flex-col items-center text-center">
      <div className="w-14 h-14 bg-surface-2 rounded-2xl flex items-center justify-center mb-4">
        <Users className="w-7 h-7 text-text-muted" />
      </div>
      <p className="text-sm font-medium text-text mb-1">Gösterilecek ekip üyesi yok</p>
      <p className="text-xs text-text-muted">Filtreleri temizlemeyi deneyin veya ekibe üye ekleyin.</p>
    </div>
  );
}

/** Team capacity table (desktop) / per-person cards (mobile, <768px) — a
 * dense heatmap-style table does not fit 390px, so mobile gets a distinct
 * card list instead of a horizontally-scrolling table. */
export function TeamCapacityGrid({ rows, loading }: TeamCapacityGridProps) {
  const columns: DataTableColumn<TeamMemberCapacityView>[] = [
    { key: "member", header: "Üye", render: (r) => <MemberIdentity row={r} />, sortValue: (r) => r.name },
    {
      key: "capacity",
      header: "Kapasite",
      align: "right",
      sortValue: (r) => r.net_capacity_minutes,
      render: (r) =>
        r.capacity_status_reason !== "ok" ? (
          <span className="text-xs text-text-muted">—</span>
        ) : (
          <span className="text-sm text-text tabular-nums">{formatMinutesAsHours(r.net_capacity_minutes)}</span>
        ),
    },
    {
      key: "planned",
      header: "Planlanan",
      align: "right",
      sortValue: (r) => r.planned_minutes,
      render: (r) => (
        <span className="text-sm text-text tabular-nums">
          {formatMinutesAsHours(r.planned_minutes)} · %{r.planned_utilization_pct}
        </span>
      ),
    },
    {
      key: "actual",
      header: "Gerçekleşen",
      align: "right",
      sortValue: (r) => r.actual_minutes,
      render: (r) => (
        <span className="text-sm text-text tabular-nums inline-flex items-center gap-1.5 justify-end">
          {formatMinutesAsHours(r.actual_minutes)} · %{r.actual_utilization_pct}
          {r.open_timer_minutes > 0 && <Timer className="w-3 h-3 text-success" />}
        </span>
      ),
    },
    {
      key: "status",
      header: "Durum",
      sortValue: (r) => r.planned_utilization_pct,
      render: (r) => <CapacityStatusBadge status={r.planned_status} reason={r.capacity_status_reason} />,
    },
    {
      key: "brands",
      header: "Markalar",
      render: (r) =>
        r.brandNames.length === 0 ? (
          <span className="text-xs text-text-muted">—</span>
        ) : (
          <div className="flex flex-wrap gap-1 max-w-[220px]">
            {r.brandNames.slice(0, 3).map((b) => (
              <span
                key={b}
                className="px-1.5 py-0.5 rounded-full bg-surface-2 border border-border text-[10px] text-text-secondary"
              >
                {b}
              </span>
            ))}
            {r.brandNames.length > 3 && (
              <span className="text-[10px] text-text-muted">+{r.brandNames.length - 3}</span>
            )}
          </div>
        ),
    },
  ];

  if (loading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-16 bg-surface-2 rounded-xl animate-pulse" />
        ))}
      </div>
    );
  }

  if (rows.length === 0) {
    return <EmptyState />;
  }

  return (
    <>
      <div className="hidden md:block">
        <DataTable columns={columns} data={rows} rowKey={(r) => r.user_id} pageSize={25} />
      </div>

      <div className="md:hidden flex flex-col gap-3">
        {rows.map((r) => (
          <div key={r.user_id} className="bg-surface border border-border rounded-xl p-4">
            <MemberIdentity row={r} />
            <div className="grid grid-cols-2 gap-3 mt-3">
              <div className="bg-surface-2 rounded-lg p-2.5">
                <p className="text-[10px] text-text-muted mb-0.5">Net Kapasite</p>
                <p className="text-sm font-semibold text-text tabular-nums">
                  {r.capacity_status_reason !== "ok" ? "—" : formatMinutesAsHours(r.net_capacity_minutes)}
                </p>
              </div>
              <div className="bg-surface-2 rounded-lg p-2.5">
                <p className="text-[10px] text-text-muted mb-0.5">Kalan</p>
                <p className="text-sm font-semibold text-text tabular-nums">
                  {r.capacity_status_reason !== "ok"
                    ? "—"
                    : formatMinutesAsHours(Math.max(0, r.net_capacity_minutes - r.planned_minutes))}
                </p>
              </div>
              <div className="bg-surface-2 rounded-lg p-2.5">
                <p className="text-[10px] text-text-muted mb-0.5">Planlanan</p>
                <p className="text-sm font-semibold text-text tabular-nums">
                  {formatMinutesAsHours(r.planned_minutes)} · %{r.planned_utilization_pct}
                </p>
              </div>
              <div className="bg-surface-2 rounded-lg p-2.5">
                <p className="text-[10px] text-text-muted mb-0.5">Gerçekleşen</p>
                <p className="text-sm font-semibold text-text tabular-nums">
                  {formatMinutesAsHours(r.actual_minutes)} · %{r.actual_utilization_pct}
                </p>
              </div>
            </div>
            <div className="mt-3 flex items-center justify-between gap-2">
              <CapacityStatusBadge status={r.planned_status} reason={r.capacity_status_reason} />
              {r.brandNames.length > 0 && (
                <span className="text-[11px] text-text-muted truncate max-w-[140px]">
                  {r.brandNames.join(", ")}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

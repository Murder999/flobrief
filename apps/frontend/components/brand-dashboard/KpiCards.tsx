"use client";

import Link from "next/link";
import type { BrandKPIStats, BriefRead } from "@/lib/api-client";
import { countDraft, countRevisionLast7Days, countCompletedThisWeek, countPendingApproval } from "./shared";
import { Package, Clock, RotateCcw, CheckCircle } from "lucide-react";
import { cn } from "@/lib/utils";

type LucideIcon = React.ComponentType<{ className?: string }>;

interface SubMetric {
  label: string;
  value: number;
}

function Kpi({
  label, value, icon: Icon, accentCls, href, subs,
}: {
  label: string;
  value: number;
  icon: LucideIcon;
  accentCls: string;
  href: string;
  subs: SubMetric[];
}) {
  return (
    <Link
      href={href}
      className="group flex flex-col gap-2.5 rounded-xl border border-border bg-surface p-4 transition-all duration-200 hover:border-accent/25 hover:shadow-card-hover"
    >
      <div className="flex items-center justify-between">
        <div className={cn("flex h-8 w-8 items-center justify-center rounded-lg", accentCls)}>
          <Icon className="h-4 w-4" />
        </div>
        <span className="text-[11px] font-medium text-text-muted opacity-0 transition-opacity group-hover:opacity-100">
          Detay →
        </span>
      </div>
      <div>
        <p className="text-2xl font-bold leading-none tracking-tight text-text">{value.toLocaleString("tr-TR")}</p>
        <p className="mt-1.5 text-[12.5px] text-text-muted">{label}</p>
      </div>
      {subs.length > 0 && (
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-t border-border pt-2">
          {subs.map((s) => (
            <div key={s.label} className="flex items-baseline gap-1">
              <span className="text-xs font-semibold text-text">{s.value}</span>
              <span className="text-[10.5px] text-text-muted">{s.label}</span>
            </div>
          ))}
        </div>
      )}
    </Link>
  );
}

function KpiSkeleton() {
  return <div className="h-[104px] animate-pulse rounded-xl border border-border bg-surface" />;
}

export function KpiCards({ kpis, briefs }: { kpis: BrandKPIStats | null; briefs: BriefRead[] | null }) {
  if (!kpis || !briefs) {
    return (
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <KpiSkeleton />
        <KpiSkeleton />
        <KpiSkeleton />
        <KpiSkeleton />
      </div>
    );
  }

  const pendingApproval = countPendingApproval(kpis, briefs);

  return (
    <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
      <Kpi
        label="Toplam Brief"
        value={kpis.total_briefs}
        icon={Package}
        accentCls="bg-accent/12 text-accent"
        href="/brand/briefs"
        subs={[
          { label: "üretimde", value: kpis.in_production },
          { label: "taslak", value: countDraft(briefs) },
        ]}
      />
      <Kpi
        label="Onay Süreci"
        value={pendingApproval}
        icon={Clock}
        accentCls="bg-amber-500/12 text-amber-500"
        href="/brand/approvals"
        subs={[
          { label: "teslim bekliyor", value: kpis.pending_deliverables },
          { label: "teslim onaylandı", value: kpis.approved_deliverables },
        ]}
      />
      <Kpi
        label="Revizyon"
        value={kpis.revision_requested}
        icon={RotateCcw}
        accentCls="bg-orange-500/12 text-orange-500"
        href="/brand/briefs?status=revision_requested"
        subs={[{ label: "son 7 gün", value: countRevisionLast7Days(briefs) }]}
      />
      <Kpi
        label="Onaylanan"
        value={kpis.approved}
        icon={CheckCircle}
        accentCls={cn(
          "bg-emerald-500/12 text-emerald-500",
          kpis.overdue_briefs > 0 && "bg-red-500/15 text-red-500"
        )}
        href="/brand/briefs?status=approved"
        subs={[
          { label: "geciken", value: kpis.overdue_briefs },
          { label: "bu hafta tamam.", value: countCompletedThisWeek(briefs) },
        ]}
      />
    </div>
  );
}

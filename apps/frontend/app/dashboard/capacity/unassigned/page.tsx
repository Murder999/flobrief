"use client";

import { CapacityNavTabs } from "@/components/capacity/CapacityNavTabs";
import { UnassignedWorkPanel } from "@/components/capacity/UnassignedWorkPanel";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { canViewTeamCapacity, getRangeForScale, type CapacityScale } from "@/lib/capacity";
import { cn } from "@/lib/utils";
import { useMemo, useState } from "react";

const SCALE_OPTIONS: { value: CapacityScale; label: string }[] = [
  { value: "daily", label: "Günlük" },
  { value: "weekly", label: "Haftalık" },
  { value: "monthly", label: "Aylık" },
];

export default function UnassignedWorkPage() {
  const { accessToken } = useAuth();
  const { activeAgency, isInitialized } = useWorkspace();
  const agencyId = activeAgency?.id ?? null;
  const role = activeAgency?.member_role ?? null;
  const [scale, setScale] = useState<CapacityScale>("weekly");
  const range = useMemo(() => getRangeForScale(scale), [scale]);

  if (!isInitialized) return null;

  if (!canViewTeamCapacity(role)) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <CapacityNavTabs />
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <p className="text-sm font-medium text-text mb-1">Bu sayfayı görüntüleme yetkiniz yok</p>
          <p className="text-xs text-text-muted">
            Atanmamış işleri görmek için ekip kapasitesi görüntüleme yetkisi gereklidir.
          </p>
        </div>
      </div>
    );
  }

  if (!agencyId || !accessToken) return null;

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <CapacityNavTabs />

      <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-text">Atanmamış İşler</h1>
          <p className="text-sm text-text-muted mt-1">
            Sahibi olmayan brief ve görevler, tahmini süreleri ve uygun ekip üyesi önerileri.
          </p>
        </div>
        <div className="flex items-center gap-1 bg-surface-2 border border-border rounded-lg p-1">
          {SCALE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setScale(opt.value)}
              className={cn(
                "px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                scale === opt.value ? "bg-accent text-white" : "text-text-muted hover:text-text"
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <UnassignedWorkPanel agencyId={agencyId} accessToken={accessToken} startDate={range.start} endDate={range.end} />
    </div>
  );
}

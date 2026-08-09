"use client";

import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { timeReportApi, type BriefTimeSummary } from "@/lib/api-client";
import { Clock } from "lucide-react";
import { useEffect, useState } from "react";

interface BriefEstimateBadgeProps {
  briefId: string;
}

/** Header badge showing actual vs. estimated hours for a brief — always
 * computed live from real TimeEntry rows via the backend, never fabricated
 * or stored client-side. Renders nothing when the brief has no estimate and
 * no logged time, so it never clutters briefs that don't use time tracking. */
export function BriefEstimateBadge({ briefId }: BriefEstimateBadgeProps) {
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();
  const agencyId = activeAgency?.id ?? null;
  const [summary, setSummary] = useState<BriefTimeSummary | null>(null);

  useEffect(() => {
    if (!accessToken || !agencyId || !briefId) return;
    let cancelled = false;
    timeReportApi
      .getBriefSummary(briefId, agencyId, accessToken)
      .then((data) => {
        if (!cancelled) setSummary(data);
      })
      .catch(() => {
        if (!cancelled) setSummary(null);
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, agencyId, briefId]);

  if (!summary || (summary.estimated_hours === null && summary.actual_hours === 0)) {
    return null;
  }

  const isOver = summary.is_over_estimate;

  return (
    <span
      title={
        summary.estimated_hours !== null
          ? `${summary.actual_hours}s kaydedildi / ${summary.estimated_hours}s tahmini`
          : `${summary.actual_hours}s kaydedildi (tahmin yok)`
      }
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium border ${
        isOver
          ? "bg-danger/10 text-danger border-danger/25"
          : "bg-surface-2 text-text-secondary border-border"
      }`}
    >
      <Clock className="w-3 h-3" />
      {summary.estimated_hours !== null
        ? `${summary.actual_hours}s / ${summary.estimated_hours}s`
        : `${summary.actual_hours}s`}
    </span>
  );
}

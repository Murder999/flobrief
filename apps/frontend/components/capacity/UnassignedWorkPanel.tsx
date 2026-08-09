"use client";

import {
  agencyApi,
  briefApi,
  capacityApi,
  type AgencyMemberRead,
  type BriefRead,
  type TeamCapacityMember,
  type UnassignedWorkItem,
} from "@/lib/api-client";
import { BRIEF_PRIORITY_BADGE_VARIANT, BRIEF_PRIORITY_LABEL, formatMinutesAsHours } from "@/lib/capacity";
import { ListChecks, Users } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

interface UnassignedWorkPanelProps {
  agencyId: string;
  accessToken: string;
  startDate: string;
  endDate: string;
}

interface EnrichedItem extends UnassignedWorkItem {
  brief?: BriefRead;
}

interface Suggestion {
  userId: string;
  name: string;
  remainingMinutes: number;
}

/** Sahibi olmayan brief/görevleri listeler. `UnassignedWorkReport` only
 * carries brief/task title + minutes/has_estimate (see
 * apps/backend/app/schemas/capacity_report.py `UnassignedWorkItem`) — brand,
 * due date and priority are enriched here from the real `BriefRead` for
 * each item's `brief_id` (no fabricated fields). "Suggested team members"
 * are derived only from the real team capacity report: status
 * available/balanced, a real schedule (`capacity_status_reason === "ok"`,
 * which already excludes people fully on time-off), and enough remaining
 * minutes for the estimate — never an AI guess. */
export function UnassignedWorkPanel({ agencyId, accessToken, startDate, endDate }: UnassignedWorkPanelProps) {
  const [items, setItems] = useState<EnrichedItem[] | null>(null);
  const [teamReport, setTeamReport] = useState<TeamCapacityMember[]>([]);
  const [members, setMembers] = useState<AgencyMemberRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [report, team, mems] = await Promise.all([
        capacityApi.getUnassignedReport(agencyId, accessToken, { start_date: startDate, end_date: endDate }),
        capacityApi
          .getTeamReport(agencyId, accessToken, { start_date: startDate, end_date: endDate })
          .catch(() => ({ start_date: startDate, end_date: endDate, members: [] as TeamCapacityMember[] })),
        agencyApi.listMembers(agencyId, accessToken).catch(() => [] as AgencyMemberRead[]),
      ]);
      setTeamReport(team.members);
      setMembers(mems.filter((m) => m.status === "active"));

      const uniqueBriefIds = Array.from(new Set(report.items.map((i) => i.brief_id)));
      const briefs = await Promise.all(
        uniqueBriefIds.map((id) => briefApi.get(id, agencyId, accessToken).catch(() => null))
      );
      const briefById = new Map(uniqueBriefIds.map((id, idx) => [id, briefs[idx]]));

      setItems(
        report.items.map((item) => ({ ...item, brief: briefById.get(item.brief_id) ?? undefined }))
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [agencyId, accessToken, startDate, endDate]);

  useEffect(() => {
    load();
  }, [load]);

  const suggestMembers = (item: EnrichedItem): Suggestion[] => {
    return teamReport
      .filter(
        (m) =>
          m.capacity_status_reason === "ok" &&
          (m.planned_status === "available" || m.planned_status === "balanced")
      )
      .map((m) => {
        const member = members.find((mem) => mem.user_id === m.user_id);
        return {
          userId: m.user_id,
          name: member?.user_full_name ?? member?.user_email ?? m.user_name,
          remainingMinutes: Math.max(0, m.net_capacity_minutes - m.planned_minutes),
        };
      })
      .filter((s) => !item.has_estimate || s.remainingMinutes >= item.minutes)
      .sort((a, b) => b.remainingMinutes - a.remainingMinutes)
      .slice(0, 3);
  };

  if (loading) {
    return (
      <div className="flex flex-col gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-24 bg-surface-2 rounded-xl animate-pulse" />
        ))}
      </div>
    );
  }

  if (error) {
    return <div className="bg-danger/10 border border-danger/30 rounded-xl p-4 text-sm text-danger">{error}</div>;
  }

  if (!items || items.length === 0) {
    return (
      <div className="bg-surface border border-border rounded-xl p-14 flex flex-col items-center text-center">
        <div className="w-14 h-14 bg-surface-2 rounded-2xl flex items-center justify-center mb-4">
          <ListChecks className="w-7 h-7 text-text-muted" />
        </div>
        <p className="text-sm font-medium text-text mb-1">Atanmamış iş yok</p>
        <p className="text-xs text-text-muted">Bu dönemde sahibi olmayan brief veya görev bulunmuyor.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {items.map((item, idx) => {
        const suggestions = suggestMembers(item);
        return (
          <div key={`${item.brief_id}-${item.task_id ?? idx}`} className="bg-surface border border-border rounded-xl p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <Link
                  href={`/dashboard/briefs/${item.brief_id}`}
                  className="text-sm font-medium text-text hover:text-accent hover:underline"
                >
                  {item.task_title ? `${item.brief_title} · ${item.task_title}` : item.brief_title}
                </Link>
                <div className="flex flex-wrap items-center gap-2 mt-1.5">
                  {item.brief?.priority && (
                    <span
                      className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${BRIEF_PRIORITY_BADGE_VARIANT[item.brief.priority] ?? "status-neutral"}`}
                    >
                      {BRIEF_PRIORITY_LABEL[item.brief.priority] ?? item.brief.priority}
                    </span>
                  )}
                  {item.brief?.deadline && (
                    <span className="text-[11px] text-text-muted">
                      Teslim: {new Date(item.brief.deadline).toLocaleDateString("tr-TR")}
                    </span>
                  )}
                  {item.brief?.content_types && item.brief.content_types.length > 0 && (
                    <span className="text-[11px] text-text-muted">{item.brief.content_types.join(", ")}</span>
                  )}
                </div>
              </div>
              <div className="text-right flex-shrink-0">
                <p className="text-sm font-semibold text-text tabular-nums">
                  {item.has_estimate ? formatMinutesAsHours(item.minutes) : "—"}
                </p>
                <p className="text-[11px] text-text-muted">
                  {item.has_estimate ? "tahmini süre" : "Süre tahmini yapılmamış"}
                </p>
              </div>
            </div>

            {suggestions.length > 0 && (
              <div className="mt-3 pt-3 border-t border-border flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1 text-[11px] text-text-muted">
                  <Users className="w-3 h-3" />
                  Uygun ekip üyeleri:
                </span>
                {suggestions.map((s) => (
                  <Link
                    key={s.userId}
                    href={`/dashboard/capacity/${s.userId}`}
                    className="text-[11px] px-2 py-0.5 rounded-full bg-surface-2 border border-border text-text-secondary hover:border-accent/40 transition-colors"
                  >
                    {s.name} · {formatMinutesAsHours(s.remainingMinutes)} müsait
                  </Link>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

"use client";

import Link from "next/link";
import { FileText } from "lucide-react";
import type { BriefRead } from "@/lib/api-client";
import { BriefStatusBadge } from "@/components/briefs/brief-status-badge";
import { isOverdue, fmtShortDate, fmtRelative } from "./shared";
import { useLocale } from "@/context/locale-context";

function RowSkeleton() {
  return (
    <div className="flex items-center gap-3 px-4 py-2.5 border-b border-border last:border-0 animate-pulse">
      <div className="flex-1 space-y-1.5">
        <div className="h-3.5 w-44 rounded bg-surface-2" />
        <div className="h-2.5 w-28 rounded bg-surface-2" />
      </div>
      <div className="h-5 w-20 rounded-md bg-surface-2" />
    </div>
  );
}

export function RecentBriefsCard({ briefs, error, onRetry }: {
  briefs: BriefRead[] | null;
  error: boolean;
  onRetry: () => void;
}) {
  const { t } = useLocale();
  const recent = briefs
    ? [...new Map(briefs.map((b) => [b.id, b])).values()]
        .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
        .slice(0, 5)
    : [];

  return (
    <div className="flex h-full flex-col rounded-xl border border-border bg-surface overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <h2 className="text-sm font-semibold text-text">{t("dashboard.brand.recentBriefs")}</h2>
        <Link href="/brand/briefs" className="text-xs text-accent hover:underline">
          {t("dashboard.brand.viewAllBriefs")}
        </Link>
      </div>

      {error ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 px-4 py-6 text-center">
          <p className="text-[13px] text-danger">{t("dashboard.brand.loadFailed")}</p>
          <button onClick={onRetry} className="text-xs text-accent hover:underline">{t("common.actions.retry")}</button>
        </div>
      ) : briefs === null ? (
        <>
          <RowSkeleton />
          <RowSkeleton />
          <RowSkeleton />
        </>
      ) : recent.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 px-4 py-6 text-center">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-surface-2">
            <FileText className="h-4 w-4 text-text-muted" />
          </div>
          <p className="text-[13px] font-medium text-text">{t("dashboard.brand.emptyBriefs")}</p>
          <p className="text-[11.5px] text-text-muted">{t("dashboard.brand.emptyBriefsBody")}</p>
        </div>
      ) : (
        <div>
          {recent.map((brief) => {
            const od = isOverdue(brief.deadline, brief.status);
            return (
              <Link
                key={brief.id}
                href={`/brand/briefs/${brief.id}`}
                className="group flex items-center gap-3 px-4 py-2.5 border-b border-border last:border-0 hover:bg-surface-2 transition-colors"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13px] font-medium text-text group-hover:text-accent">{brief.title}</p>
                  <p className={`mt-0.5 text-[11px] ${od ? "font-medium text-danger" : "text-text-muted"}`}>
                    {brief.deadline ? `${t("dashboard.brand.deadline", { date: fmtShortDate(brief.deadline) })}${od ? ` · ${t("dashboard.brand.overdueLabel")}` : ""} · ` : ""}
                    {fmtRelative(brief.updated_at)}
                  </p>
                </div>
                <BriefStatusBadge status={brief.status} />
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

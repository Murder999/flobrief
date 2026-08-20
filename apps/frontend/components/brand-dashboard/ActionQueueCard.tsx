"use client";

import Link from "next/link";
import { CheckCircle2, ChevronRight } from "lucide-react";
import type { BriefRead } from "@/lib/api-client";
import { BriefPriorityBadge } from "@/components/briefs/brief-status-badge";
import { deriveActionItems, waitingSinceLabel, fmtShortDate } from "./shared";
import { useLocale } from "@/context/locale-context";

function RowSkeleton() {
  return (
    <div className="flex items-center gap-3 px-4 py-3 border-b border-border last:border-0 animate-pulse">
      <div className="h-2 w-2 rounded-full bg-surface-2" />
      <div className="flex-1 space-y-1.5">
        <div className="h-3.5 w-40 rounded bg-surface-2" />
        <div className="h-2.5 w-24 rounded bg-surface-2" />
      </div>
      <div className="h-5 w-16 rounded-md bg-surface-2" />
    </div>
  );
}

export function ActionQueueCard({ briefs }: { briefs: BriefRead[] | null }) {
  const { t } = useLocale();
  const items = briefs ? deriveActionItems(briefs) : null;
  const visible = items?.slice(0, 4) ?? [];

  return (
    <div className="flex h-full flex-col rounded-xl border border-border bg-surface overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-text">{t("dashboard.brand.actionQueue")}</h2>
          {items !== null && items.length > 0 && (
            <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-danger px-1 text-[10px] font-bold text-white">
              {items.length}
            </span>
          )}
        </div>
        {items !== null && items.length > 4 && (
          <Link href="/brand/approvals" className="text-xs text-accent hover:underline">
            {t("dashboard.brand.viewAllActions", { count: items.length })}
          </Link>
        )}
      </div>

      {briefs === null ? (
        <>
          <RowSkeleton />
          <RowSkeleton />
        </>
      ) : items && items.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 px-4 py-6 text-center">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500/10">
            <CheckCircle2 className="h-4.5 w-4.5 text-emerald-500" />
          </div>
          <p className="text-[13px] font-medium text-text">{t("dashboard.brand.noPending")}</p>
          <p className="text-[11.5px] text-text-muted">{t("dashboard.brand.upToDate")}</p>
        </div>
      ) : (
        <div>
          {visible.map(({ brief, ctaLabel, reasonLabel, reasonCls, overdue }) => (
            <Link
              key={brief.id}
              href={`/brand/briefs/${brief.id}`}
              className="group flex items-center gap-3 px-4 py-2.5 border-b border-border last:border-0 hover:bg-surface-2 transition-colors"
            >
              <span className={`h-2 w-2 flex-shrink-0 rounded-full ${overdue ? "bg-danger animate-pulse" : "bg-amber-400"}`} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-medium text-text group-hover:text-accent">{brief.title}</p>
                <div className="mt-0.5 flex items-center gap-2 text-[11px] text-text-muted">
                  {brief.deadline && <span>{t("dashboard.brand.deadline", { date: fmtShortDate(brief.deadline) })}</span>}
                  <span>·</span>
                  <span>{waitingSinceLabel(brief)}</span>
                  <BriefPriorityBadge priority={brief.priority} />
                </div>
              </div>
              <span className={`flex-shrink-0 text-[11.5px] font-medium ${reasonCls}`}>{reasonLabel}</span>
              <span className="flex-shrink-0 rounded-md bg-accent-subtle px-2 py-1 text-[11px] font-medium text-accent">
                {ctaLabel}
              </span>
              <ChevronRight className="h-3.5 w-3.5 flex-shrink-0 text-text-muted opacity-0 transition-opacity group-hover:opacity-100" />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

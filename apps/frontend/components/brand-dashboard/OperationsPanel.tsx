"use client";

import Link from "next/link";
import { Users, CheckCircle, Calendar, FolderOpen, PlusSquare } from "lucide-react";
import type { BrandTeamUsage } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { useLocale } from "@/context/locale-context";

interface QuickAction {
  href: string;
  label: string;
  icon: typeof Users;
  iconCls: string;
  hint?: string;
}

export function OperationsPanel({
  teamUsage, pendingApprovalCount, overdueCount, approvedDeliverables, pendingDeliverables,
}: {
  teamUsage: BrandTeamUsage | null;
  pendingApprovalCount: number;
  overdueCount: number;
  approvedDeliverables: number;
  pendingDeliverables: number;
}) {
  const { t } = useLocale();
  const quickActions: QuickAction[] = [
    { href: "/brand/approvals", label: t("dashboard.brand.reviewApprovals"), icon: CheckCircle, iconCls: "bg-accent/10 text-accent", hint: pendingApprovalCount > 0 ? t("dashboard.brand.approvalsHint", { count: pendingApprovalCount }) : undefined },
    { href: "/brand/briefs/new", label: t("dashboard.brand.newBrief"), icon: PlusSquare, iconCls: "bg-indigo-500/10 text-indigo-400" },
    { href: "/brand/calendar", label: t("dashboard.brand.viewCalendar"), icon: Calendar, iconCls: "bg-blue-500/10 text-blue-400" },
    { href: "/brand/files", label: t("dashboard.brand.files"), icon: FolderOpen, iconCls: "bg-emerald-500/10 text-emerald-400" },
  ];

  const healthLines: string[] = [];
  const healthy = pendingApprovalCount === 0 && overdueCount === 0;
  if (healthy) {
    healthLines.push(t("dashboard.brand.healthNormal"));
  } else {
    if (pendingApprovalCount > 0) healthLines.push(t("dashboard.brand.actionsWaiting", { count: pendingApprovalCount }));
    if (overdueCount > 0) healthLines.push(t("dashboard.brand.briefsOverdue", { count: overdueCount }));
  }
  const deliverableTotal = pendingDeliverables + approvedDeliverables;
  const deliverableRatio = deliverableTotal > 0 ? Math.round((approvedDeliverables / deliverableTotal) * 100) : null;

  return (
    <div className="sticky top-6 flex flex-col gap-4">
      {teamUsage && (
        <div className="rounded-xl border border-border bg-surface p-4">
          <div className="mb-3 flex items-center gap-2">
            <Users className="h-4 w-4 text-accent" />
            <h2 className="text-[13px] font-semibold text-text">{t("dashboard.brand.teamPlan")}</h2>
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-[11.5px] text-text-muted">{t("dashboard.brand.seats")}</span>
              <span className="text-xs font-semibold text-text">
                {teamUsage.users.used} / {teamUsage.users.limit ?? t("dashboard.brand.unlimited")}
              </span>
            </div>
            {teamUsage.users.pending_invites > 0 && (
              <div className="flex items-center justify-between">
                <span className="text-[11.5px] text-text-muted">{t("dashboard.brand.pendingInvites")}</span>
                <span className="text-xs font-semibold text-text">{teamUsage.users.pending_invites}</span>
              </div>
            )}
            {teamUsage.users.limit !== null && teamUsage.users.available !== null && teamUsage.users.available <= 0 && (
              <p className="text-[11px] font-medium text-warning">{t("dashboard.brand.seatLimit")}</p>
            )}
            {teamUsage.plan_name && <p className="pt-0.5 text-[10.5px] text-text-muted/70">{t("dashboard.brand.plan", { plan: teamUsage.plan_name })}</p>}
          </div>
          <Link href="/brand/team" className="mt-2.5 block text-xs text-accent hover:underline">
            {t("dashboard.brand.manageTeam")}
          </Link>
        </div>
      )}

      <div className="rounded-xl border border-border bg-surface p-4">
        <h2 className="mb-3 text-[13px] font-semibold text-text">{t("dashboard.actions.title")}</h2>
        <div className="space-y-1">
          {quickActions.map((action) => (
            <Link
              key={action.href}
              href={action.href}
              className="flex items-center gap-2.5 rounded-lg px-2 py-2 transition-colors hover:bg-surface-2"
            >
              <span className={cn("flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg", action.iconCls)}>
                <action.icon className="h-3.5 w-3.5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[12.5px] font-medium text-text">{action.label}</p>
                {action.hint && <p className="truncate text-[10.5px] text-text-muted">{action.hint}</p>}
              </div>
            </Link>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-border bg-surface p-4">
        <h2 className="mb-2.5 text-[13px] font-semibold text-text">{t("dashboard.brand.health")}</h2>
        <div className="space-y-1">
          {healthLines.map((line) => (
            <p key={line} className={cn("text-[12px]", healthy ? "text-emerald-500" : "text-text")}>
              {line}
            </p>
          ))}
        </div>
        {deliverableRatio !== null && (
          <div className="mt-3">
            <div className="mb-1 flex items-center justify-between text-[10.5px] text-text-muted">
              <span>{t("dashboard.brand.deliveryRate")}</span>
              <span>{deliverableRatio}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-surface-2">
              <div
                className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-400 transition-all"
                style={{ width: `${deliverableRatio}%` }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

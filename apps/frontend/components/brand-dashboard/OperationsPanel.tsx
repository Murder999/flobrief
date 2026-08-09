"use client";

import Link from "next/link";
import { Users, CheckCircle, Calendar, FolderOpen, PlusSquare } from "lucide-react";
import type { BrandTeamUsage } from "@/lib/api-client";
import { cn } from "@/lib/utils";

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
  const quickActions: QuickAction[] = [
    { href: "/brand/approvals", label: "Onayları İncele", icon: CheckCircle, iconCls: "bg-accent/10 text-accent", hint: pendingApprovalCount > 0 ? `${pendingApprovalCount} onay bekliyor` : undefined },
    { href: "/brand/briefs/new", label: "Yeni Brief Ver", icon: PlusSquare, iconCls: "bg-indigo-500/10 text-indigo-400" },
    { href: "/brand/calendar", label: "Takvimi Gör", icon: Calendar, iconCls: "bg-blue-500/10 text-blue-400" },
    { href: "/brand/files", label: "Dosyalar", icon: FolderOpen, iconCls: "bg-emerald-500/10 text-emerald-400" },
  ];

  const healthLines: string[] = [];
  if (pendingApprovalCount === 0 && overdueCount === 0) {
    healthLines.push("Süreçler normal");
  } else {
    if (pendingApprovalCount > 0) healthLines.push(`${pendingApprovalCount} aksiyon bekliyor`);
    if (overdueCount > 0) healthLines.push(`${overdueCount} brief son tarihi geçti`);
  }
  const deliverableTotal = pendingDeliverables + approvedDeliverables;
  const deliverableRatio = deliverableTotal > 0 ? Math.round((approvedDeliverables / deliverableTotal) * 100) : null;

  return (
    <div className="sticky top-6 flex flex-col gap-4">
      {teamUsage && (
        <div className="rounded-xl border border-border bg-surface p-4">
          <div className="mb-3 flex items-center gap-2">
            <Users className="h-4 w-4 text-accent" />
            <h2 className="text-[13px] font-semibold text-text">Ekip ve Plan</h2>
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-[11.5px] text-text-muted">Koltuk</span>
              <span className="text-xs font-semibold text-text">
                {teamUsage.users.used} / {teamUsage.users.limit ?? "sınırsız"}
              </span>
            </div>
            {teamUsage.users.pending_invites > 0 && (
              <div className="flex items-center justify-between">
                <span className="text-[11.5px] text-text-muted">Bekleyen davet</span>
                <span className="text-xs font-semibold text-text">{teamUsage.users.pending_invites}</span>
              </div>
            )}
            {teamUsage.users.limit !== null && teamUsage.users.available !== null && teamUsage.users.available <= 0 && (
              <p className="text-[11px] font-medium text-warning">Koltuk limitine ulaşıldı</p>
            )}
            {teamUsage.plan_name && <p className="pt-0.5 text-[10.5px] text-text-muted/70">Plan: {teamUsage.plan_name}</p>}
          </div>
          <Link href="/brand/team" className="mt-2.5 block text-xs text-accent hover:underline">
            Ekibi yönet →
          </Link>
        </div>
      )}

      <div className="rounded-xl border border-border bg-surface p-4">
        <h2 className="mb-3 text-[13px] font-semibold text-text">Hızlı İşlemler</h2>
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
        <h2 className="mb-2.5 text-[13px] font-semibold text-text">Operasyon Sağlığı</h2>
        <div className="space-y-1">
          {healthLines.map((line) => (
            <p key={line} className={cn("text-[12px]", line === "Süreçler normal" ? "text-emerald-500" : "text-text")}>
              {line}
            </p>
          ))}
        </div>
        {deliverableRatio !== null && (
          <div className="mt-3">
            <div className="mb-1 flex items-center justify-between text-[10.5px] text-text-muted">
              <span>Teslim onay oranı</span>
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

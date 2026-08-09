"use client";

import type { BriefStatus, BriefPriority } from "@/lib/api-client";
import { cn } from "@/lib/utils";

const STATUS_CONFIG: Record<BriefStatus, { label: string; className: string }> = {
  draft:             { label: "Taslak",             className: "status-neutral" },
  submitted:         { label: "Gönderildi",         className: "status-accent" },
  in_review:         { label: "İncelemede",         className: "status-info" },
  accepted:          { label: "Kabul Edildi",       className: "status-purple" },
  in_production:     { label: "Üretimde",           className: "status-purple" },
  ready_for_review:  { label: "İncelemeye Hazır",  className: "status-info" },
  revision_requested:{ label: "Revizyon İstendi",  className: "status-danger" },
  approved:          { label: "Onaylandı",          className: "status-success" },
  completed:         { label: "Tamamlandı",         className: "status-success" },
  scheduled:         { label: "Takvime Alındı",    className: "status-warning" },
  archived:          { label: "Arşivlendi",         className: "status-neutral opacity-60" },
};

const PRIORITY_CONFIG: Record<BriefPriority, { label: string; dot: string; labelClass: string }> = {
  low:    { label: "Düşük",  dot: "bg-text-muted/40", labelClass: "text-text-muted" },
  normal: { label: "Normal", dot: "bg-info",           labelClass: "text-info-text" },
  high:   { label: "Yüksek", dot: "bg-warning",        labelClass: "text-warning-text" },
  urgent: { label: "Acil",   dot: "bg-danger",         labelClass: "text-danger-text" },
};

interface StatusBadgeProps {
  status: BriefStatus;
  className?: string;
}

export function BriefStatusBadge({ status, className = "" }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.draft;
  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium",
        config.className,
        className
      )}
    >
      {config.label}
    </span>
  );
}

interface PriorityBadgeProps {
  priority: BriefPriority;
  className?: string;
}

export function BriefPriorityBadge({ priority, className = "" }: PriorityBadgeProps) {
  const config = PRIORITY_CONFIG[priority] ?? PRIORITY_CONFIG.normal;
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs", config.labelClass, className)}>
      <span className={cn("w-1.5 h-1.5 rounded-full flex-shrink-0", config.dot)} />
      {config.label}
    </span>
  );
}

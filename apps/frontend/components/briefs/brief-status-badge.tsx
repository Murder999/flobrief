"use client";

import type { BriefStatus, BriefPriority } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { useLocale } from "@/context/locale-context";
import type { TranslationKey } from "@/messages";

const STATUS_CONFIG: Record<BriefStatus, { labelKey: TranslationKey; className: string }> = {
  draft:             { labelKey: "briefs.status.draft",             className: "status-neutral" },
  submitted:         { labelKey: "briefs.status.submitted",         className: "status-accent" },
  in_review:         { labelKey: "briefs.status.inReview",          className: "status-info" },
  accepted:          { labelKey: "briefs.status.accepted",          className: "status-purple" },
  in_production:     { labelKey: "briefs.status.inProduction",      className: "status-purple" },
  ready_for_review:  { labelKey: "briefs.status.readyForReview",    className: "status-info" },
  revision_requested:{ labelKey: "briefs.status.revisionRequested", className: "status-danger" },
  approved:          { labelKey: "briefs.status.approved",          className: "status-success" },
  completed:         { labelKey: "briefs.status.completed",         className: "status-success" },
  scheduled:         { labelKey: "briefs.status.scheduled",         className: "status-warning" },
  archived:          { labelKey: "briefs.status.archived",          className: "status-neutral opacity-60" },
};

const PRIORITY_CONFIG: Record<BriefPriority, { labelKey: TranslationKey; dot: string; labelClass: string }> = {
  low:    { labelKey: "briefs.priority.low",    dot: "bg-text-muted/40", labelClass: "text-text-muted" },
  normal: { labelKey: "briefs.priority.normal", dot: "bg-info",           labelClass: "text-info-text" },
  high:   { labelKey: "briefs.priority.high",   dot: "bg-warning",        labelClass: "text-warning-text" },
  urgent: { labelKey: "briefs.priority.urgent", dot: "bg-danger",         labelClass: "text-danger-text" },
};

interface StatusBadgeProps {
  status: BriefStatus;
  className?: string;
}

export function BriefStatusBadge({ status, className = "" }: StatusBadgeProps) {
  const { t } = useLocale();
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.draft;
  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium",
        config.className,
        className
      )}
    >
      {t(config.labelKey)}
    </span>
  );
}

interface PriorityBadgeProps {
  priority: BriefPriority;
  className?: string;
}

export function BriefPriorityBadge({ priority, className = "" }: PriorityBadgeProps) {
  const { t } = useLocale();
  const config = PRIORITY_CONFIG[priority] ?? PRIORITY_CONFIG.normal;
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs", config.labelClass, className)}>
      <span className={cn("w-1.5 h-1.5 rounded-full flex-shrink-0", config.dot)} />
      {t(config.labelKey)}
    </span>
  );
}

import { AlertOctagon, AlertTriangle, CheckCircle2, Gauge, HelpCircle } from "lucide-react";
import {
  CAPACITY_REASON_LABEL,
  CAPACITY_STATUS_COLOR,
  CAPACITY_STATUS_LABEL,
  type CapacityStatus,
  type CapacityStatusReason,
} from "@/lib/capacity";

const ICONS: Record<CapacityStatus, typeof CheckCircle2> = {
  available: CheckCircle2,
  balanced: Gauge,
  near_capacity: AlertTriangle,
  overloaded: AlertOctagon,
  unknown: HelpCircle,
};

const KNOWN_STATUSES = new Set<string>(Object.keys(CAPACITY_STATUS_LABEL));
const KNOWN_REASONS = new Set<string>(Object.keys(CAPACITY_REASON_LABEL));

interface CapacityStatusBadgeProps {
  status: string;
  reason?: string;
  className?: string;
}

/** Icon + Turkish text status pill — capacity status is never rendered as
 * color alone anywhere in the capacity UI (product rule). When
 * `capacity_status_reason` is not "ok" the reason text (e.g. "İzinli")
 * takes over instead of a possibly-misleading status label. */
export function CapacityStatusBadge({ status, reason, className }: CapacityStatusBadgeProps) {
  const hasSpecialReason = !!reason && reason !== "ok" && KNOWN_REASONS.has(reason);
  const statusKey: CapacityStatus = KNOWN_STATUSES.has(status) ? (status as CapacityStatus) : "unknown";
  const key: CapacityStatus = hasSpecialReason ? "unknown" : statusKey;
  const label = hasSpecialReason
    ? CAPACITY_REASON_LABEL[reason as CapacityStatusReason]
    : CAPACITY_STATUS_LABEL[statusKey];
  const Icon = ICONS[key];

  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs font-medium ${CAPACITY_STATUS_COLOR[key]} ${className ?? ""}`}
    >
      <Icon className="w-3.5 h-3.5 flex-shrink-0" />
      {label}
    </span>
  );
}

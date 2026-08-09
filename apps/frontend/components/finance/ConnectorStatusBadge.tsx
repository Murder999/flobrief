import { AlertTriangle, CheckCircle2, CircleDashed } from "lucide-react";
import type { ConnectorStatusValue } from "@/lib/api-client";
import { CONNECTOR_STATUS_COLOR, CONNECTOR_STATUS_LABEL } from "@/lib/finance";

const ICONS: Record<ConnectorStatusValue, typeof CheckCircle2> = {
  not_configured: CircleDashed,
  connected: CheckCircle2,
  error: AlertTriangle,
};

interface ConnectorStatusBadgeProps {
  status: string;
  className?: string;
}

/** Icon + Turkish text status pill — never color alone, mirrors
 * `InvoiceStatusBadge`/`CapacityStatusBadge`. Falls back to
 * `not_configured` styling only if the backend ever ships a status this UI
 * doesn't know about yet (never shows a bare enum value in the normal
 * case). */
export function ConnectorStatusBadge({ status, className }: ConnectorStatusBadgeProps) {
  const known = status in CONNECTOR_STATUS_LABEL;
  const key = (known ? status : "not_configured") as ConnectorStatusValue;
  const Icon = ICONS[key];
  const label = known ? CONNECTOR_STATUS_LABEL[key] : status;

  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs font-medium ${CONNECTOR_STATUS_COLOR[key]} ${className ?? ""}`}
    >
      <Icon className="w-3.5 h-3.5 flex-shrink-0" />
      {label}
    </span>
  );
}

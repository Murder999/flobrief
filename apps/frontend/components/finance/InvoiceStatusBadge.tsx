import {
  AlertCircle,
  Ban,
  CheckCircle2,
  Clock,
  FileEdit,
  Loader2,
  Send,
  Wallet,
  XCircle,
} from "lucide-react";
import type { ClientInvoiceStatusValue } from "@/lib/api-client";
import { INVOICE_STATUS_COLOR, INVOICE_STATUS_LABEL } from "@/lib/finance";

const ICONS: Record<ClientInvoiceStatusValue, typeof CheckCircle2> = {
  draft: FileEdit,
  pending_approval: Clock,
  approved: CheckCircle2,
  sending: Loader2,
  sent: Send,
  partially_paid: Wallet,
  paid: CheckCircle2,
  overdue: AlertCircle,
  cancelled: Ban,
  failed: XCircle,
};

interface InvoiceStatusBadgeProps {
  status: string;
  className?: string;
}

/** Icon + Turkish text status pill — never color-only, mirrors
 * `CapacityStatusBadge`. Falls back to the raw value only if the backend
 * ever ships a status this UI doesn't know about yet (never shows a bare
 * enum value in the normal case). */
export function InvoiceStatusBadge({ status, className }: InvoiceStatusBadgeProps) {
  const known = status in INVOICE_STATUS_LABEL;
  const key = (known ? status : "draft") as ClientInvoiceStatusValue;
  const Icon = ICONS[key];
  const label = known ? INVOICE_STATUS_LABEL[key] : status;

  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs font-medium ${INVOICE_STATUS_COLOR[key]} ${className ?? ""}`}
    >
      <Icon className={`w-3.5 h-3.5 flex-shrink-0 ${status === "sending" ? "animate-spin" : ""}`} />
      {label}
    </span>
  );
}

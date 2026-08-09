import { cn } from "@/lib/utils";
import { AlertTriangle, Lock } from "lucide-react";

interface MissingRateLabelProps {
  text: string;
  /** true = permission-hidden (no COST_RATE_VIEW) -> Lock icon, muted
   * color. false = data genuinely missing (no cost/billing rate configured
   * yet) -> AlertTriangle icon, warning color. Mirrors
   * `lib/finance.ts`'s `costMissingInfo().hidden` flag one-to-one — never
   * rendered as a bare 0/blank in either case (plan §7/§13, this phase's
   * design requirement), and the two cases are visually distinct since
   * they call for different user actions ("ask an Owner" vs "configure a
   * rate"). */
  hidden?: boolean;
  className?: string;
}

export function MissingRateLabel({ text, hidden = false, className }: MissingRateLabelProps) {
  const Icon = hidden ? Lock : AlertTriangle;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-xs font-medium",
        hidden ? "text-text-muted" : "text-warning",
        className
      )}
    >
      <Icon className="w-3.5 h-3.5 flex-shrink-0" />
      {text}
    </span>
  );
}

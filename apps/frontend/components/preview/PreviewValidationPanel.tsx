"use client";

import { Info, AlertTriangle } from "lucide-react";
import type { PreviewWarning } from "@/lib/api-client";
import { cn } from "@/lib/utils";

interface PreviewValidationPanelProps {
  warnings: PreviewWarning[];
}

/** Renders warnings computed by the backend's preview_validation_service —
 * explicitly labelled as internal heuristics, never presented as an
 * enforced platform limit (the real platforms can change their limits at
 * any time; this panel only flags things worth a second look). */
export function PreviewValidationPanel({ warnings }: PreviewValidationPanelProps) {
  if (warnings.length === 0) return null;

  return (
    <div className="rounded-xl border border-border bg-surface-2 px-3.5 py-3 space-y-2">
      <p className="text-[10.5px] font-semibold uppercase tracking-wide text-text-muted">
        Dahili öneriler · gerçek platform sınırları değildir
      </p>
      <ul className="space-y-1.5">
        {warnings.map((w, i) => (
          <li
            key={`${w.code}-${i}`}
            className={cn(
              "flex items-start gap-2 text-[12px] leading-snug",
              w.severity === "warning" ? "text-amber-700" : "text-text-muted",
            )}
          >
            {w.severity === "warning" ? (
              <AlertTriangle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
            ) : (
              <Info className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
            )}
            <span>{w.message}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

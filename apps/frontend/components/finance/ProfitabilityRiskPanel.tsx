"use client";

import type { ProfitabilityRiskFlag } from "@/lib/api-client";
import { PROFITABILITY_RISK_LABEL } from "@/lib/finance";
import { AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";

interface ProfitabilityRiskPanelProps {
  riskFlags: ProfitabilityRiskFlag[];
  brandNames: Record<string, string>;
  onSelect: (flag: ProfitabilityRiskFlag) => void;
}

const RISK_COLOR: Record<string, string> = {
  dusuk_kar_marji: "border-warning/30 bg-warning/10 text-warning",
  negatif_kar_marji: "border-danger/30 bg-danger/10 text-danger",
  retainer_asimi: "border-danger/30 bg-danger/10 text-danger",
  yuksek_faturalanmamis_is: "border-warning/30 bg-warning/10 text-warning",
  gecikmis_fatura: "border-danger/30 bg-danger/10 text-danger",
};

const COLLAPSED_LIMIT = 6;

/** Small, clickable risk chips — deliberately compact (plan §11's "Riskler
 * bölümü... boğmamalı, tıklanınca ilgili filtre açılmalı"): never a full
 * table, capped to `COLLAPSED_LIMIT` rows with an expand toggle, and every
 * chip is a button that jumps to + filters the brand table for that brand
 * (`onSelect`), not just static text. Icon + text always, never color
 * alone, matching `InvoiceStatusBadge`/`RetainerSummaryCard`'s convention. */
export function ProfitabilityRiskPanel({ riskFlags, brandNames, onSelect }: ProfitabilityRiskPanelProps) {
  const [expanded, setExpanded] = useState(false);
  if (riskFlags.length === 0) return null;

  const visible = expanded ? riskFlags : riskFlags.slice(0, COLLAPSED_LIMIT);
  const hiddenCount = riskFlags.length - visible.length;

  return (
    <div className="bg-surface border border-border rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <AlertTriangle className="w-4 h-4 text-warning flex-shrink-0" />
        <h3 className="text-sm font-semibold text-text">Riskler</h3>
        <span className="text-xs text-text-muted">({riskFlags.length})</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {visible.map((flag, i) => (
          <button
            key={`${flag.type}-${flag.brand_id ?? "agency"}-${i}`}
            type="button"
            onClick={() => onSelect(flag)}
            title={flag.message}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-[12px] font-medium transition-opacity hover:opacity-80 ${
              RISK_COLOR[flag.type] ?? "border-border bg-surface-2 text-text-muted"
            }`}
          >
            <span>{PROFITABILITY_RISK_LABEL[flag.type] ?? flag.type}</span>
            {flag.brand_id && (
              <span className="opacity-70">· {brandNames[flag.brand_id] ?? "Marka"}</span>
            )}
          </button>
        ))}
      </div>
      {riskFlags.length > COLLAPSED_LIMIT && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="mt-2 inline-flex items-center gap-1 text-[12px] font-medium text-text-muted hover:text-text transition-colors"
        >
          {expanded ? (
            <>
              <ChevronUp className="w-3.5 h-3.5" /> Daha Az Göster
            </>
          ) : (
            <>
              <ChevronDown className="w-3.5 h-3.5" /> {hiddenCount} Daha Fazla
            </>
          )}
        </button>
      )}
    </div>
  );
}

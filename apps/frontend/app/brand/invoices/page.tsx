"use client";

import { InvoiceStatusBadge } from "@/components/finance/InvoiceStatusBadge";
import { useAuth } from "@/hooks/useAuth";
import { brandPortalApi, type BrandInvoiceRead } from "@/lib/api-client";
import { DOCUMENT_TYPE_LABEL, formatDate, formatMoneyCents } from "@/lib/finance";
import { Receipt } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

function InvoiceRowSkeleton() {
  return (
    <div className="bg-surface border border-border rounded-xl p-5 animate-pulse">
      <div className="flex items-center justify-between">
        <div className="space-y-2 flex-1">
          <div className="h-4 bg-surface-2 rounded w-1/3" />
          <div className="h-3 bg-surface-2 rounded w-1/4" />
        </div>
        <div className="h-5 w-24 bg-surface-2 rounded-full" />
      </div>
    </div>
  );
}

/** Read-only brand-portal invoice list (plan §9's Phase-5 gap closure).
 * The backend's `GET /brand-portal/invoices` already excludes
 * draft/pending_approval/cancelled invoices server-side — every row shown
 * here is one the agency has actually sent. */
export default function BrandInvoicesPage() {
  const { accessToken } = useAuth();
  const [invoices, setInvoices] = useState<BrandInvoiceRead[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!accessToken) return;
    setError(null);
    try {
      const data = await brandPortalApi.listInvoices(accessToken, { limit: 100 });
      setInvoices(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Faturalar yüklenemedi");
      setInvoices([]);
    }
  }, [accessToken]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-text">Faturalar</h1>
        <p className="text-sm text-text-muted mt-1">
          Ajansınızın sizinle paylaştığı fatura taslakları ve durumları.
        </p>
      </div>

      {error ? (
        <div className="bg-danger/10 border border-danger/30 rounded-xl p-4 text-sm text-danger">
          {error}
        </div>
      ) : invoices === null ? (
        <div className="space-y-3">
          <InvoiceRowSkeleton />
          <InvoiceRowSkeleton />
          <InvoiceRowSkeleton />
        </div>
      ) : invoices.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center bg-surface border border-border rounded-xl">
          <div className="w-16 h-16 bg-surface-2 rounded-2xl flex items-center justify-center mb-4">
            <Receipt className="w-7 h-7 text-text-muted" />
          </div>
          <p className="text-base font-medium text-text mb-1">Henüz fatura yok</p>
          <p className="text-sm text-text-muted max-w-sm">
            Ajansınız sizinle bir fatura paylaştığında burada görüntülenecek.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {invoices.map((inv) => (
            <Link
              key={inv.id}
              href={`/brand/invoices/${inv.id}`}
              className="bg-surface border border-border rounded-xl p-5 hover:border-accent/40 hover:shadow-card transition-all flex items-center justify-between gap-4"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-sm font-medium text-text">{inv.invoice_number}</p>
                  <span className="text-[11px] text-text-muted px-1.5 py-0.5 rounded-full bg-surface-2 border border-border">
                    {DOCUMENT_TYPE_LABEL[inv.document_type]}
                  </span>
                </div>
                <p className="text-xs text-text-muted mt-1">Vade: {formatDate(inv.due_date)}</p>
              </div>
              <div className="flex items-center gap-4 flex-shrink-0">
                <span className="text-sm font-semibold text-text tabular-nums">
                  {formatMoneyCents(inv.total_cents, inv.currency)}
                </span>
                <InvoiceStatusBadge status={inv.status} />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

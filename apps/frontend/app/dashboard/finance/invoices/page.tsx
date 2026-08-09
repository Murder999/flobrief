"use client";

import { InvoiceStatusBadge } from "@/components/finance/InvoiceStatusBadge";
import { Select } from "@/components/ui/select";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { agencyApi, financeApi, type BrandRead, type ClientInvoiceRead } from "@/lib/api-client";
import { DOCUMENT_TYPE_LABEL, INVOICE_STATUS_LABEL, formatDate, formatMoneyCents } from "@/lib/finance";
import { Receipt } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

const STATUS_OPTIONS = [
  { value: "", label: "Tüm Durumlar" },
  ...Object.entries(INVOICE_STATUS_LABEL).map(([value, label]) => ({ value, label })),
];

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

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <div className="w-16 h-16 bg-surface-2 rounded-2xl flex items-center justify-center mb-4">
        <Receipt className="w-7 h-7 text-text-muted" />
      </div>
      <p className="text-base font-medium text-text mb-1">Henüz fatura yok</p>
      <p className="text-sm text-text-muted mb-6">
        Faturalandırılabilir zaman kayıtlarını seçerek ilk fatura taslağınızı oluşturun.
      </p>
      <Link
        href="/dashboard/finance/billable-time"
        className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors"
      >
        Faturalandırılabilir Zamana Git
      </Link>
    </div>
  );
}

export default function InvoicesListPage() {
  const { accessToken } = useAuth();
  const { activeAgency, isInitialized } = useWorkspace();
  const agencyId = activeAgency?.id ?? null;

  const [brands, setBrands] = useState<BrandRead[]>([]);
  const [brandFilter, setBrandFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");

  const [items, setItems] = useState<ClientInvoiceRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken || !agencyId) return;
    agencyApi
      .listBrands(agencyId, accessToken)
      .then(setBrands)
      .catch(() => {});
  }, [accessToken, agencyId]);

  const brandNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const b of brands) map[b.id] = b.name;
    return map;
  }, [brands]);

  const load = useCallback(async () => {
    if (!accessToken || !agencyId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await financeApi.listInvoices(agencyId, accessToken, {
        brand_id: brandFilter || undefined,
        status: statusFilter || undefined,
        limit: 100,
      });
      setItems(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Faturalar yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [accessToken, agencyId, brandFilter, statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  if (!isInitialized || !agencyId || !accessToken) return null;

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-text">Faturalar</h1>
        <p className="text-sm text-text-muted mt-1">
          Marka bazında fatura taslakları ve yaşam döngüsü — resmi e-fatura değil, dahili belgedir.
        </p>
      </div>

      <div className="flex flex-wrap gap-4 mb-6">
        <div className="w-full sm:w-56">
          <Select
            label="Marka"
            value={brandFilter}
            onChange={(e) => setBrandFilter(e.target.value)}
            options={[{ value: "", label: "Tüm Markalar" }, ...brands.map((b) => ({ value: b.id, label: b.name }))]}
          />
        </div>
        <div className="w-full sm:w-56">
          <Select
            label="Durum"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            options={STATUS_OPTIONS}
          />
        </div>
      </div>

      {error ? (
        <div className="bg-danger/10 border border-danger/30 rounded-xl p-4 text-sm text-danger">{error}</div>
      ) : loading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <InvoiceRowSkeleton key={i} />
          ))}
        </div>
      ) : items.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="flex flex-col gap-3">
          {items.map((inv) => (
            <Link
              key={inv.id}
              href={`/dashboard/finance/invoices/${inv.id}`}
              className="bg-surface border border-border rounded-xl p-5 hover:border-accent/40 hover:shadow-card transition-all flex items-center justify-between gap-4"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-sm font-medium text-text">{inv.invoice_number}</p>
                  <span className="text-[11px] text-text-muted px-1.5 py-0.5 rounded-full bg-surface-2 border border-border">
                    {DOCUMENT_TYPE_LABEL[inv.document_type]}
                  </span>
                </div>
                <p className="text-xs text-text-muted mt-1">
                  {brandNames[inv.brand_id] ?? "—"} · Vade: {formatDate(inv.due_date)}
                </p>
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

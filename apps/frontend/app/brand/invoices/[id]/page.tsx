"use client";

import { InvoiceStatusBadge } from "@/components/finance/InvoiceStatusBadge";
import { useAuth } from "@/hooks/useAuth";
import { ApiError, brandPortalApi, type BrandInvoiceWithLines } from "@/lib/api-client";
import { DOCUMENT_TYPE_LABEL, formatDate, formatMoneyCents } from "@/lib/finance";
import { AlertTriangle, ArrowLeft, Download, ListChecks } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.detail === "string") return e.detail;
    return e.message;
  }
  return e instanceof Error ? e.message : "Fatura yüklenemedi";
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/** Read-only brand-portal invoice detail, including per-line service
 * breakdown via `GET /brand-portal/invoices/{id}`. Same visibility rules as
 * the list (only non-draft/non-pending/non-cancelled invoices are ever
 * returned — a 404 here means "not visible to this brand", not necessarily
 * "doesn't exist"). Line items use `BrandInvoiceLineRead`, which by
 * construction on the backend excludes cost/margin fields. */
export default function BrandInvoiceDetailPage() {
  const params = useParams();
  const invoiceId = params.id as string;
  const { accessToken } = useAuth();

  const [invoice, setInvoice] = useState<BrandInvoiceWithLines | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const load = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    setNotFound(false);
    try {
      const found = await brandPortalApi.getInvoice(invoiceId, accessToken);
      setInvoice(found);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setNotFound(true);
      } else {
        setError(errorMessage(e));
      }
    } finally {
      setLoading(false);
    }
  }, [accessToken, invoiceId]);

  useEffect(() => {
    load();
  }, [load]);

  const handlePdf = async () => {
    if (!accessToken || !invoice) return;
    setDownloading(true);
    try {
      const blob = await brandPortalApi.downloadInvoicePdf(invoice.id, accessToken);
      downloadBlob(blob, `fatura-${invoice.invoice_number}.pdf`);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setDownloading(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 max-w-3xl mx-auto animate-pulse">
        <div className="h-7 bg-surface-2 rounded w-1/2 mb-3" />
        <div className="h-4 bg-surface-2 rounded w-1/3 mb-8" />
        <div className="h-64 bg-surface-2 rounded-xl" />
      </div>
    );
  }

  if (error || notFound || !invoice) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <Link
          href="/brand/invoices"
          className="text-sm text-text-muted hover:text-text inline-flex items-center gap-1.5 mb-4"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Faturalara Dön
        </Link>
        <div className="bg-danger/10 border border-danger/30 rounded-xl p-4 text-sm text-danger">
          {error ?? "Fatura bulunamadı"}
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-3xl mx-auto space-y-6">
      <Link
        href="/brand/invoices"
        className="text-sm text-text-muted hover:text-text inline-flex items-center gap-1.5"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        Faturalara Dön
      </Link>

      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-2xl font-semibold text-text">{invoice.invoice_number}</h1>
            <InvoiceStatusBadge status={invoice.status} />
          </div>
          <p className="text-sm text-text-muted mt-1">
            Düzenleme: {formatDate(invoice.issue_date)} · Vade: {formatDate(invoice.due_date)}
          </p>
        </div>
        <span className="text-2xl font-bold text-text tabular-nums">
          {formatMoneyCents(invoice.total_cents, invoice.currency)}
        </span>
      </div>

      <div className="flex items-start gap-2 px-4 py-3 rounded-lg bg-warning/10 border border-warning/20 text-xs text-warning">
        <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
        <span>
          Bu belge <strong>{DOCUMENT_TYPE_LABEL[invoice.document_type]}</strong> niteliğindedir ve
          resmi/geçerli bir e-fatura değildir — yalnızca dahili takip ve müşteri iletişimi
          amaçlıdır.
        </span>
      </div>

      <button
        onClick={handlePdf}
        disabled={downloading}
        className="inline-flex items-center gap-2 px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors disabled:opacity-50"
      >
        <Download className="w-3.5 h-3.5" />
        {downloading ? "İndiriliyor…" : "PDF İndir"}
      </button>

      {invoice.notes && (
        <div className="bg-surface border border-border rounded-xl p-4 text-sm text-text-secondary">
          {invoice.notes}
        </div>
      )}

      {invoice.lines.length > 0 && (
        <div className="bg-surface border border-border rounded-xl p-5">
          <h3 className="text-sm font-semibold text-text mb-3 flex items-center gap-2">
            <ListChecks className="w-4 h-4 text-text-muted" />
            Hizmet Kalemleri
          </h3>

          <div className="hidden md:block overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-surface-2 border-b border-border">
                  <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                    Açıklama
                  </th>
                  <th className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                    Miktar
                  </th>
                  <th className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                    Birim Fiyat
                  </th>
                  <th className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                    KDV
                  </th>
                  <th className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                    Toplam
                  </th>
                </tr>
              </thead>
              <tbody>
                {invoice.lines.map((line) => (
                  <tr key={line.id} className="border-b border-border last:border-0">
                    <td className="px-3 py-2.5 text-text">
                      {line.description}
                      {(line.service_period_start || line.service_period_end) && (
                        <p className="text-[11px] text-text-muted mt-0.5">
                          {line.service_period_start ? formatDate(line.service_period_start) : "—"}
                          {" – "}
                          {line.service_period_end ? formatDate(line.service_period_end) : "—"}
                        </p>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-right text-text-secondary tabular-nums">
                      {line.quantity} {line.unit}
                    </td>
                    <td className="px-3 py-2.5 text-right text-text-secondary tabular-nums">
                      {formatMoneyCents(line.unit_price_cents, invoice.currency)}
                    </td>
                    <td className="px-3 py-2.5 text-right text-text-secondary tabular-nums">
                      %{(line.tax_rate_bps / 100).toFixed(0)}
                    </td>
                    <td className="px-3 py-2.5 text-right text-text font-medium tabular-nums">
                      {formatMoneyCents(line.total_cents, invoice.currency)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="md:hidden flex flex-col gap-2.5">
            {invoice.lines.map((line) => (
              <div key={line.id} className="bg-surface-2 border border-border rounded-lg p-3.5">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm font-medium text-text min-w-0">{line.description}</p>
                  <span className="text-sm font-semibold text-text tabular-nums flex-shrink-0">
                    {formatMoneyCents(line.total_cents, invoice.currency)}
                  </span>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-text-muted">
                  <span>
                    {line.quantity} {line.unit} × {formatMoneyCents(line.unit_price_cents, invoice.currency)}
                  </span>
                  <span>KDV %{(line.tax_rate_bps / 100).toFixed(0)}</span>
                  {(line.service_period_start || line.service_period_end) && (
                    <span>
                      {line.service_period_start ? formatDate(line.service_period_start) : "—"}
                      {" – "}
                      {line.service_period_end ? formatDate(line.service_period_end) : "—"}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-surface border border-border rounded-xl p-5">
        <h3 className="text-sm font-semibold text-text mb-3">Tutar Özeti</h3>
        <div className="space-y-1.5 text-sm">
          <div className="flex justify-between text-text-muted">
            <span>Ara Toplam</span>
            <span className="tabular-nums">{formatMoneyCents(invoice.subtotal_cents, invoice.currency)}</span>
          </div>
          {invoice.discount_cents > 0 && (
            <div className="flex justify-between text-text-muted">
              <span>İndirim</span>
              <span className="tabular-nums">-{formatMoneyCents(invoice.discount_cents, invoice.currency)}</span>
            </div>
          )}
          <div className="flex justify-between text-text-muted">
            <span>KDV</span>
            <span className="tabular-nums">{formatMoneyCents(invoice.tax_cents, invoice.currency)}</span>
          </div>
          <div className="flex justify-between font-semibold text-text pt-1.5 border-t border-border">
            <span>Toplam</span>
            <span className="tabular-nums">{formatMoneyCents(invoice.total_cents, invoice.currency)}</span>
          </div>
          {invoice.amount_paid_cents > 0 && (
            <div className="flex justify-between text-success">
              <span>Ödenen</span>
              <span className="tabular-nums">{formatMoneyCents(invoice.amount_paid_cents, invoice.currency)}</span>
            </div>
          )}
        </div>
      </div>

      {(invoice.billing_contact_name || invoice.billing_contact_email || invoice.tax_office || invoice.tax_number) && (
        <div className="bg-surface border border-border rounded-xl p-5">
          <h3 className="text-sm font-semibold text-text mb-3">Fatura Bilgileri</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
            {invoice.billing_contact_name && (
              <div>
                <p className="text-xs text-text-muted">İletişim Kişisi</p>
                <p className="text-text">{invoice.billing_contact_name}</p>
              </div>
            )}
            {invoice.billing_contact_email && (
              <div>
                <p className="text-xs text-text-muted">E-posta</p>
                <p className="text-text">{invoice.billing_contact_email}</p>
              </div>
            )}
            {invoice.tax_office && (
              <div>
                <p className="text-xs text-text-muted">Vergi Dairesi</p>
                <p className="text-text">{invoice.tax_office}</p>
              </div>
            )}
            {invoice.tax_number && (
              <div>
                <p className="text-xs text-text-muted">Vergi Numarası</p>
                <p className="text-text">{invoice.tax_number}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

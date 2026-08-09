"use client";

import { InvoiceDraftBuilder } from "@/components/finance/InvoiceDraftBuilder";
import { InvoiceStatusBadge } from "@/components/finance/InvoiceStatusBadge";
import { PaymentRecordForm } from "@/components/finance/PaymentRecordForm";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import {
  agencyApi,
  ApiError,
  financeApi,
  type BrandRead,
  type ClientInvoiceWithLines,
} from "@/lib/api-client";
import {
  DOCUMENT_TYPE_LABEL,
  canManageInvoices,
  canManagePayments,
  canViewPayments,
  formatDate,
  formatMoneyCents,
} from "@/lib/finance";
import { AlertTriangle, ArrowLeft, Ban, CheckCircle2, Download, FileDown, Send } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.detail === "string") return e.detail;
    return e.message;
  }
  return e instanceof Error ? e.message : "İşlem başarısız";
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

export default function InvoiceDetailPage() {
  const params = useParams();
  const invoiceId = params.id as string;
  const { accessToken } = useAuth();
  const { activeAgency, isInitialized } = useWorkspace();
  const { toast, confirm } = useToast();
  const agencyId = activeAgency?.id ?? null;
  const role = activeAgency?.member_role ?? null;
  const canManage = canManageInvoices(role);
  const canViewInvoicePayments = canViewPayments(role);
  const canManageInvoicePayments = canManagePayments(role);

  const [invoice, setInvoice] = useState<ClientInvoiceWithLines | null>(null);
  const [brand, setBrand] = useState<BrandRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!accessToken || !agencyId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await financeApi.getInvoice(invoiceId, agencyId, accessToken);
      setInvoice(data);
      const brands = await agencyApi.listBrands(agencyId, accessToken).catch(() => []);
      setBrand(brands.find((b) => b.id === data.brand_id) ?? null);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [accessToken, agencyId, invoiceId]);

  useEffect(() => {
    load();
  }, [load]);

  const runAction = async (
    action: "approve" | "send" | "void",
    fn: () => Promise<ClientInvoiceWithLines>,
    successMsg: string
  ) => {
    if (action === "void") {
      const ok = await confirm({
        title: "Faturayı İptal Et",
        message: "Bu faturayı iptal etmek istediğinize emin misiniz? İlişkili zaman kayıtları yeniden faturalandırılabilir hale gelir.",
        confirmLabel: "İptal Et",
        destructive: true,
      });
      if (!ok) return;
    }
    setActionLoading(action);
    try {
      const updated = await fn();
      setInvoice(updated);
      toast(successMsg, "success");
    } catch (e) {
      toast(errorMessage(e), "error");
    } finally {
      setActionLoading(null);
    }
  };

  const handlePdf = async () => {
    if (!accessToken || !agencyId || !invoice) return;
    setActionLoading("pdf");
    try {
      const blob = await financeApi.downloadInvoicePdf(invoice.id, agencyId, accessToken);
      downloadBlob(blob, `fatura-${invoice.invoice_number}.pdf`);
    } catch (e) {
      toast(errorMessage(e), "error");
    } finally {
      setActionLoading(null);
    }
  };

  const handleCsv = async () => {
    if (!accessToken || !agencyId || !invoice) return;
    setActionLoading("csv");
    try {
      const blob = await financeApi.downloadInvoiceCsv(invoice.id, agencyId, accessToken);
      downloadBlob(blob, `fatura-${invoice.invoice_number}.csv`);
    } catch (e) {
      toast(errorMessage(e), "error");
    } finally {
      setActionLoading(null);
    }
  };

  if (!isInitialized || !agencyId || !accessToken) return null;

  if (loading) {
    return (
      <div className="p-8 max-w-4xl mx-auto animate-pulse">
        <div className="h-7 bg-surface-2 rounded w-1/2 mb-3" />
        <div className="h-4 bg-surface-2 rounded w-1/3 mb-8" />
        <div className="h-64 bg-surface-2 rounded-xl" />
      </div>
    );
  }

  if (error || !invoice) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <Link href="/dashboard/finance/invoices" className="text-sm text-text-muted hover:text-text inline-flex items-center gap-1.5 mb-4">
          <ArrowLeft className="w-3.5 h-3.5" />
          Faturalara Dön
        </Link>
        <div className="bg-danger/10 border border-danger/30 rounded-xl p-4 text-sm text-danger">
          {error ?? "Fatura bulunamadı"}
        </div>
      </div>
    );
  }

  const canApprove = canManage && invoice.status === "draft";
  const canSend = canManage && invoice.status === "approved";
  const canVoid = canManage && ["draft", "pending_approval", "approved"].includes(invoice.status);

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">
      <Link href="/dashboard/finance/invoices" className="text-sm text-text-muted hover:text-text inline-flex items-center gap-1.5">
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
            {brand?.name ?? "—"} · Düzenleme: {formatDate(invoice.issue_date)} · Vade: {formatDate(invoice.due_date)}
          </p>
        </div>
        <span className="text-2xl font-bold text-text tabular-nums">
          {formatMoneyCents(invoice.total_cents, invoice.currency)}
        </span>
      </div>

      <div className="flex items-start gap-2 px-4 py-3 rounded-lg bg-warning/10 border border-warning/20 text-xs text-warning">
        <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
        <span>
          Bu belge <strong>{DOCUMENT_TYPE_LABEL[invoice.document_type]}</strong> niteliğindedir ve resmi/geçerli bir
          e-fatura değildir — yalnızca dahili takip ve müşteri iletişimi amaçlıdır.
        </span>
      </div>

      <div className="flex flex-wrap gap-2">
        {canApprove && (
          <Button size="sm" onClick={() => runAction("approve", () => financeApi.approveInvoice(invoice.id, agencyId, accessToken), "Fatura onaylandı.")} isLoading={actionLoading === "approve"}>
            <CheckCircle2 className="w-3.5 h-3.5" />
            Onayla
          </Button>
        )}
        {canSend && (
          <Button size="sm" onClick={() => runAction("send", () => financeApi.sendInvoice(invoice.id, agencyId, accessToken), "Fatura gönderildi.")} isLoading={actionLoading === "send"}>
            <Send className="w-3.5 h-3.5" />
            Gönder
          </Button>
        )}
        <Button size="sm" variant="secondary" onClick={handlePdf} isLoading={actionLoading === "pdf"}>
          <Download className="w-3.5 h-3.5" />
          PDF İndir
        </Button>
        <Button size="sm" variant="secondary" onClick={handleCsv} isLoading={actionLoading === "csv"}>
          <FileDown className="w-3.5 h-3.5" />
          CSV İndir
        </Button>
        {canVoid && (
          <Button
            size="sm"
            variant="destructive"
            onClick={() => runAction("void", () => financeApi.voidInvoice(invoice.id, agencyId, accessToken), "Fatura iptal edildi.")}
            isLoading={actionLoading === "void"}
          >
            <Ban className="w-3.5 h-3.5" />
            İptal Et
          </Button>
        )}
      </div>

      {invoice.notes && (
        <div className="bg-surface border border-border rounded-xl p-4 text-sm text-text-secondary">{invoice.notes}</div>
      )}

      <InvoiceDraftBuilder
        invoice={invoice}
        agencyId={agencyId}
        accessToken={accessToken}
        canManage={canManage}
        onChanged={(updated) => setInvoice(updated)}
      />

      {canViewInvoicePayments && (
        <PaymentRecordForm
          invoice={invoice}
          agencyId={agencyId}
          accessToken={accessToken}
          canView={canViewInvoicePayments}
          canManage={canManageInvoicePayments}
          onRecorded={load}
        />
      )}

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

"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Drawer } from "@/components/ui/drawer";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import {
  ApiError,
  financeApi,
  type ClientInvoiceWithLines,
  type PaymentMethodValue,
  type PaymentRead,
} from "@/lib/api-client";
import {
  FINANCE_CURRENCIES,
  PAYMENT_METHOD_LABEL,
  formatMoneyCents,
  unitsToCents,
} from "@/lib/finance";
import { AlertTriangle, Plus, Wallet } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

type InvoiceForPayment = Pick<
  ClientInvoiceWithLines,
  "id" | "brand_id" | "currency" | "total_cents" | "amount_paid_cents"
>;

interface PaymentRecordFormProps {
  invoice: InvoiceForPayment;
  agencyId: string;
  accessToken: string;
  canView: boolean;
  canManage: boolean;
  /** Called after a payment is successfully recorded so the parent page can
   * re-fetch the invoice — `PaymentService.record_payment` updates
   * `amount_paid_cents`/`status` server-side, so the invoice shown above
   * this section goes stale otherwise. */
  onRecorded: () => void;
}

const METHOD_OPTIONS = Object.entries(PAYMENT_METHOD_LABEL).map(([value, label]) => ({
  value,
  label,
}));

function emptyForm(currency: string) {
  return {
    amount: "",
    currency,
    payment_method: "bank_transfer" as PaymentMethodValue,
    paid_at: new Date().toISOString().slice(0, 16),
    external_payment_id: "",
    notes: "",
    allowOverpayment: false,
  };
}

function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.detail === "string") return e.detail;
    return e.message;
  }
  return e instanceof Error ? e.message : "Ödeme kaydedilemedi";
}

function fmtDateTime(iso: string): string {
  return new Date(iso).toLocaleString("tr-TR", { dateStyle: "medium", timeStyle: "short" });
}

/** Payment recording + history for one `ClientInvoice`. `PAYMENT_VIEW`
 * gates the list, `PAYMENT_MANAGE` gates the recording action (plan §8,
 * frontend UX gating only — the backend `require_permission` dependency is
 * the real gate). Uses the `Drawer` primitive per plan §14/§11. */
export function PaymentRecordForm({
  invoice,
  agencyId,
  accessToken,
  canView,
  canManage,
  onRecorded,
}: PaymentRecordFormProps) {
  const { toast } = useToast();
  const [payments, setPayments] = useState<PaymentRead[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [form, setForm] = useState(emptyForm(invoice.currency));
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const remaining = invoice.total_cents - invoice.amount_paid_cents;

  const load = useCallback(async () => {
    if (!canView) return;
    setLoading(true);
    setError(null);
    try {
      const data = await financeApi.listPayments(agencyId, accessToken, {
        invoice_id: invoice.id,
      });
      setPayments(data);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [agencyId, accessToken, invoice.id, canView]);

  useEffect(() => {
    load();
  }, [load]);

  if (!canView) return null;

  const update = <K extends keyof ReturnType<typeof emptyForm>>(
    key: K,
    value: ReturnType<typeof emptyForm>[K]
  ) => setForm((prev) => ({ ...prev, [key]: value }));

  const openDrawer = () => {
    setForm(emptyForm(invoice.currency));
    setFormError(null);
    setDrawerOpen(true);
  };

  const amountCents = unitsToCents(form.amount) ?? 0;
  const exceedsRemaining = amountCents > 0 && remaining > 0 && amountCents > remaining;

  const handleSubmit = async () => {
    setFormError(null);
    const cents = unitsToCents(form.amount);
    if (!cents || cents <= 0) {
      setFormError("Geçerli bir tutar girin.");
      return;
    }
    if (exceedsRemaining && !form.allowOverpayment) {
      setFormError("Tutar kalan bakiyeyi aşıyor — onaylamak için kutuyu işaretleyin.");
      return;
    }
    setSaving(true);
    try {
      await financeApi.recordPayment(
        {
          brand_id: invoice.brand_id,
          invoice_id: invoice.id,
          amount_cents: cents,
          currency: form.currency,
          payment_method: form.payment_method,
          paid_at: new Date(form.paid_at).toISOString(),
          external_payment_id: form.external_payment_id.trim() || null,
          notes: form.notes.trim() || null,
          allow_overpayment: form.allowOverpayment,
        },
        agencyId,
        accessToken
      );
      toast("Ödeme kaydedildi.", "success");
      setForm(emptyForm(invoice.currency));
      setDrawerOpen(false);
      load();
      onRecorded();
    } catch (e) {
      const message = errorMessage(e);
      setFormError(message);
      toast(message, "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Ödemeler</CardTitle>
          <p className="text-xs text-text-muted mt-1">
            Kalan bakiye:{" "}
            <span className="font-medium text-text">
              {formatMoneyCents(Math.max(0, remaining), invoice.currency)}
            </span>
          </p>
        </div>
        {canManage && (
          <Button size="sm" variant="secondary" onClick={openDrawer}>
            <Plus className="w-3.5 h-3.5" />
            Ödeme Kaydet
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {error ? (
          <p className="text-sm text-danger">{error}</p>
        ) : loading ? (
          <div className="space-y-2">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="h-11 bg-surface-2 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : !payments || payments.length === 0 ? (
          <div className="flex flex-col items-center text-center py-6">
            <Wallet className="w-6 h-6 text-text-muted/50 mb-2" />
            <p className="text-sm text-text-muted">Bu fatura için henüz ödeme kaydedilmedi.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-2 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                    Tarih
                  </th>
                  <th className="px-2 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                    Yöntem
                  </th>
                  <th className="px-2 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                    Referans
                  </th>
                  <th className="px-2 py-2 text-right text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                    Tutar
                  </th>
                </tr>
              </thead>
              <tbody>
                {payments.map((p) => (
                  <tr key={p.id} className="border-b border-border last:border-0">
                    <td className="px-2 py-2.5 text-text-secondary whitespace-nowrap">
                      {fmtDateTime(p.paid_at)}
                    </td>
                    <td className="px-2 py-2.5 text-text-secondary">
                      {PAYMENT_METHOD_LABEL[p.payment_method] ?? p.payment_method}
                    </td>
                    <td className="px-2 py-2.5 text-text-secondary truncate max-w-[10rem]">
                      {p.external_payment_id || p.notes || "—"}
                    </td>
                    <td className="px-2 py-2.5 text-right font-medium text-text tabular-nums">
                      {formatMoneyCents(p.amount_cents, p.currency)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>

      <Drawer
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title="Ödeme Kaydet"
        description="Bu fatura için manuel ödeme kaydı oluşturun"
        footer={
          <>
            <Button variant="secondary" size="sm" onClick={() => setDrawerOpen(false)}>
              Vazgeç
            </Button>
            <Button size="sm" onClick={handleSubmit} isLoading={saving}>
              Kaydet
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {formError && <p className="text-sm text-danger">{formError}</p>}

          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Tutar"
              type="number"
              min={0}
              step="0.01"
              value={form.amount}
              onChange={(e) => update("amount", e.target.value)}
            />
            <Select
              label="Para Birimi"
              value={form.currency}
              onChange={(e) => update("currency", e.target.value)}
              options={FINANCE_CURRENCIES.map((c) => ({ value: c, label: c }))}
            />
          </div>

          {exceedsRemaining && (
            <div className="flex items-start gap-2 px-3 py-2.5 rounded-lg bg-warning/10 border border-warning/20 text-xs text-warning">
              <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <div>
                <p>Girilen tutar kalan bakiyeyi aşıyor.</p>
                <label className="mt-1.5 flex items-center gap-1.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.allowOverpayment}
                    onChange={(e) => update("allowOverpayment", e.target.checked)}
                  />
                  Yine de fazla ödeme olarak kaydet
                </label>
              </div>
            </div>
          )}

          <Select
            label="Ödeme Yöntemi"
            value={form.payment_method}
            onChange={(e) => update("payment_method", e.target.value as PaymentMethodValue)}
            options={METHOD_OPTIONS}
          />

          <Input
            label="Ödeme Tarihi"
            type="datetime-local"
            value={form.paid_at}
            onChange={(e) => update("paid_at", e.target.value)}
          />

          <Input
            label="Referans (opsiyonel)"
            value={form.external_payment_id}
            onChange={(e) => update("external_payment_id", e.target.value)}
            hint="ör. dekont/işlem numarası"
          />

          <Input
            label="Not (opsiyonel)"
            value={form.notes}
            onChange={(e) => update("notes", e.target.value)}
          />
        </div>
      </Drawer>
    </Card>
  );
}

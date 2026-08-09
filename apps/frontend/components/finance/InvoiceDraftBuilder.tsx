"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import {
  ApiError,
  financeApi,
  type ClientInvoiceLineRead,
  type ClientInvoiceWithLines,
} from "@/lib/api-client";
import { formatMoneyCents } from "@/lib/finance";
import { Plus, Receipt, Trash2 } from "lucide-react";
import { useState } from "react";

interface InvoiceDraftBuilderProps {
  invoice: ClientInvoiceWithLines;
  agencyId: string;
  accessToken: string;
  canManage: boolean;
  onChanged: (updated: ClientInvoiceWithLines) => void;
}

const SOURCE_TYPE_LABEL: Record<string, string> = {
  time_entry: "Zaman Kaydı",
  fixed_fee: "Sabit Ücret",
  retainer: "Retainer",
  per_item: "Birim",
  deliverable: "Teslimat",
  manual: "Manuel",
};

function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.detail === "string") return e.detail;
    return e.message;
  }
  return e instanceof Error ? e.message : "İşlem başarısız";
}

function emptyLineForm() {
  return { description: "", quantity: "1", unit: "adet", unit_price: "", tax_rate_pct: "20", discount: "0" };
}

/** Editable-while-draft line-items table for a `ClientInvoice` — manual
 * line add/remove, mirrors `CommercialTermsForm`'s controlled-form
 * conventions. Read-only once the invoice moves beyond `draft` (backend
 * also rejects line mutation past draft, this is a UX mirror only). */
export function InvoiceDraftBuilder({
  invoice,
  agencyId,
  accessToken,
  canManage,
  onChanged,
}: InvoiceDraftBuilderProps) {
  const { toast, confirm } = useToast();
  const isDraft = invoice.status === "draft";
  const editable = isDraft && canManage;

  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState(emptyLineForm());
  const [saving, setSaving] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);

  const update = <K extends keyof ReturnType<typeof emptyLineForm>>(key: K, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const handleAdd = async () => {
    const quantity = Number(form.quantity);
    const unitPrice = Number(form.unit_price);
    if (!form.description.trim() || !Number.isFinite(quantity) || quantity <= 0 || !Number.isFinite(unitPrice) || unitPrice < 0) {
      toast("Açıklama, adet ve birim fiyat gerekli.", "error");
      return;
    }
    setSaving(true);
    try {
      const updated = await financeApi.addInvoiceLine(
        invoice.id,
        {
          source_type: "manual",
          description: form.description.trim(),
          quantity,
          unit: form.unit.trim() || "adet",
          unit_price_cents: Math.round(unitPrice * 100),
          tax_rate_bps: Math.round((Number(form.tax_rate_pct) || 0) * 100),
          discount_cents: Math.round((Number(form.discount) || 0) * 100),
        },
        agencyId,
        accessToken
      );
      onChanged(updated);
      setForm(emptyLineForm());
      setAdding(false);
      toast("Kalem eklendi.", "success");
    } catch (e) {
      toast(errorMessage(e), "error");
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async (line: ClientInvoiceLineRead) => {
    const ok = await confirm({
      title: "Kalemi Kaldır",
      message: `"${line.description}" kalemini faturadan kaldırmak istediğinize emin misiniz?`,
      confirmLabel: "Kaldır",
      destructive: true,
    });
    if (!ok) return;
    setRemovingId(line.id);
    try {
      const updated = await financeApi.removeInvoiceLine(invoice.id, line.id, agencyId, accessToken);
      onChanged(updated);
      toast("Kalem kaldırıldı.", "success");
    } catch (e) {
      toast(errorMessage(e), "error");
    } finally {
      setRemovingId(null);
    }
  };

  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-border">
        <div className="flex items-center gap-2">
          <Receipt className="w-4 h-4 text-text-muted" />
          <h3 className="text-sm font-semibold text-text">Fatura Kalemleri</h3>
        </div>
        {editable && !adding && (
          <Button size="sm" variant="secondary" onClick={() => setAdding(true)}>
            <Plus className="w-3.5 h-3.5" />
            Kalem Ekle
          </Button>
        )}
      </div>

      {invoice.lines.length === 0 ? (
        <p className="px-5 py-8 text-center text-sm text-text-muted">Henüz kalem yok.</p>
      ) : (
        <>
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-surface-2 border-b border-border">
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-text-muted">Açıklama</th>
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-text-muted">Kaynak</th>
                  <th className="px-4 py-2.5 text-right text-[11px] font-semibold uppercase tracking-wide text-text-muted">Miktar</th>
                  <th className="px-4 py-2.5 text-right text-[11px] font-semibold uppercase tracking-wide text-text-muted">Birim Fiyat</th>
                  <th className="px-4 py-2.5 text-right text-[11px] font-semibold uppercase tracking-wide text-text-muted">Toplam</th>
                  {editable && <th className="px-4 py-2.5 w-10" />}
                </tr>
              </thead>
              <tbody>
                {invoice.lines.map((line) => (
                  <tr key={line.id} className="border-b border-border last:border-0">
                    <td className="px-4 py-3 text-text">{line.description}</td>
                    <td className="px-4 py-3 text-text-secondary text-xs">
                      {SOURCE_TYPE_LABEL[line.source_type] ?? line.source_type}
                    </td>
                    <td className="px-4 py-3 text-right text-text-secondary tabular-nums">
                      {line.quantity} {line.unit}
                    </td>
                    <td className="px-4 py-3 text-right text-text-secondary tabular-nums">
                      {formatMoneyCents(line.unit_price_cents, invoice.currency)}
                    </td>
                    <td className="px-4 py-3 text-right text-text font-medium tabular-nums">
                      {formatMoneyCents(line.total_cents, invoice.currency)}
                    </td>
                    {editable && (
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => handleRemove(line)}
                          disabled={removingId === line.id}
                          className="text-text-muted hover:text-danger transition-colors disabled:opacity-40"
                          aria-label="Kalemi kaldır"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="md:hidden flex flex-col gap-2 p-4">
            {invoice.lines.map((line) => (
              <div key={line.id} className="bg-surface-2 rounded-lg p-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm text-text truncate">{line.description}</p>
                    <p className="text-[11px] text-text-muted mt-0.5">
                      {SOURCE_TYPE_LABEL[line.source_type] ?? line.source_type} · {line.quantity} {line.unit}
                    </p>
                  </div>
                  {editable && (
                    <button
                      onClick={() => handleRemove(line)}
                      disabled={removingId === line.id}
                      className="text-text-muted hover:text-danger transition-colors disabled:opacity-40 flex-shrink-0"
                      aria-label="Kalemi kaldır"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
                <p className="mt-2 text-sm font-semibold text-text tabular-nums text-right">
                  {formatMoneyCents(line.total_cents, invoice.currency)}
                </p>
              </div>
            ))}
          </div>
        </>
      )}

      {editable && adding && (
        <div className="border-t border-border p-4 space-y-3 bg-surface-2/40">
          <Input label="Açıklama" value={form.description} onChange={(e) => update("description", e.target.value)} />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Input label="Miktar" type="number" min={0} step="0.01" value={form.quantity} onChange={(e) => update("quantity", e.target.value)} />
            <Input label="Birim" value={form.unit} onChange={(e) => update("unit", e.target.value)} />
            <Input
              label={`Birim Fiyat (${invoice.currency})`}
              type="number"
              min={0}
              step="0.01"
              value={form.unit_price}
              onChange={(e) => update("unit_price", e.target.value)}
            />
            <Input label="KDV (%)" type="number" min={0} max={100} step="0.1" value={form.tax_rate_pct} onChange={(e) => update("tax_rate_pct", e.target.value)} />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={() => { setAdding(false); setForm(emptyLineForm()); }}>
              Vazgeç
            </Button>
            <Button size="sm" onClick={handleAdd} isLoading={saving}>
              Kalemi Ekle
            </Button>
          </div>
        </div>
      )}

      <div className="border-t border-border px-5 py-4 space-y-1.5 bg-surface-2/30">
        <div className="flex justify-between text-xs text-text-muted">
          <span>Ara Toplam</span>
          <span className="tabular-nums">{formatMoneyCents(invoice.subtotal_cents, invoice.currency)}</span>
        </div>
        {invoice.discount_cents > 0 && (
          <div className="flex justify-between text-xs text-text-muted">
            <span>İndirim</span>
            <span className="tabular-nums">-{formatMoneyCents(invoice.discount_cents, invoice.currency)}</span>
          </div>
        )}
        <div className="flex justify-between text-xs text-text-muted">
          <span>KDV</span>
          <span className="tabular-nums">{formatMoneyCents(invoice.tax_cents, invoice.currency)}</span>
        </div>
        <div className="flex justify-between text-sm font-semibold text-text pt-1.5 border-t border-border">
          <span>Toplam</span>
          <span className="tabular-nums">{formatMoneyCents(invoice.total_cents, invoice.currency)}</span>
        </div>
        {invoice.amount_paid_cents > 0 && (
          <div className="flex justify-between text-xs text-success">
            <span>Ödenen</span>
            <span className="tabular-nums">{formatMoneyCents(invoice.amount_paid_cents, invoice.currency)}</span>
          </div>
        )}
      </div>
    </div>
  );
}

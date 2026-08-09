"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import {
  ApiError,
  financeApi,
  type CommercialTermsBillingModelValue,
  type CommercialTermsCreatePayload,
  type CommercialTermsRead,
} from "@/lib/api-client";
import {
  BILLING_MODEL_DESCRIPTION,
  BILLING_MODEL_FIELDS,
  BILLING_MODEL_LABEL,
  FINANCE_CURRENCIES,
  bpsToPct,
  centsToUnits,
  formatDate,
  formatMoneyCents,
  pctToBps,
  unitsToCents,
} from "@/lib/finance";
import { Lock, Pencil } from "lucide-react";
import { useEffect, useState } from "react";

interface CommercialTermsFormProps {
  brandId: string;
  agencyId: string;
  accessToken: string;
  currentTerms: CommercialTermsRead | null;
  canManage: boolean;
  onSaved: (terms: CommercialTermsRead) => void;
}

const MONEY_FIELD_LABEL: Record<string, string> = {
  hourly_rate_cents: "Saatlik Ücret",
  fixed_fee_cents: "Sabit Ücret",
  retainer_amount_cents: "Retainer Tutarı",
  per_item_rate_cents: "Birim Fiyatı",
  overage_rate_cents: "Aşım Oranı (saatlik)",
};

interface FormState {
  billing_model: CommercialTermsBillingModelValue;
  currency: string;
  hourly_rate: string;
  fixed_fee: string;
  retainer_amount: string;
  retainer_included_minutes: string;
  overage_rate: string;
  per_item_rate: string;
  payment_terms_days: string;
  tax_rate_pct: string;
  discount_rate_pct: string;
  billing_contact_name: string;
  billing_contact_email: string;
  billing_address_text: string;
  tax_office: string;
  tax_number: string;
  valid_from: string;
  valid_until: string;
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function emptyForm(): FormState {
  return {
    billing_model: "hourly",
    currency: "TRY",
    hourly_rate: "",
    fixed_fee: "",
    retainer_amount: "",
    retainer_included_minutes: "",
    overage_rate: "",
    per_item_rate: "",
    payment_terms_days: "30",
    tax_rate_pct: "20",
    discount_rate_pct: "",
    billing_contact_name: "",
    billing_contact_email: "",
    billing_address_text: "",
    tax_office: "",
    tax_number: "",
    valid_from: todayIso(),
    valid_until: "",
  };
}

/** Superseding a term always starts a *new* row — prior money/date values
 * are copied in as edit convenience, but `valid_from` always resets to
 * today (never re-uses the old row's start date) since the old term is
 * closed out at create time by `CommercialTermsService.create`. */
function formFromTerms(t: CommercialTermsRead): FormState {
  const addressText =
    t.billing_address && typeof t.billing_address.address === "string"
      ? (t.billing_address.address as string)
      : "";
  return {
    billing_model: t.billing_model,
    currency: t.currency,
    hourly_rate: centsToUnits(t.hourly_rate_cents),
    fixed_fee: centsToUnits(t.fixed_fee_cents),
    retainer_amount: centsToUnits(t.retainer_amount_cents),
    retainer_included_minutes: t.retainer_included_minutes?.toString() ?? "",
    overage_rate: centsToUnits(t.overage_rate_cents),
    per_item_rate: centsToUnits(t.per_item_rate_cents),
    payment_terms_days: String(t.payment_terms_days),
    tax_rate_pct: bpsToPct(t.tax_rate_bps) || "0",
    discount_rate_pct: bpsToPct(t.discount_rate_bps),
    billing_contact_name: t.billing_contact_name ?? "",
    billing_contact_email: t.billing_contact_email ?? "",
    billing_address_text: addressText,
    tax_office: t.tax_office ?? "",
    tax_number: t.tax_number ?? "",
    valid_from: todayIso(),
    valid_until: "",
  };
}

function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.detail === "string") return e.detail;
    return e.message;
  }
  return e instanceof Error ? e.message : "Kaydedilemedi";
}

/** Commercial-terms section of the finance settings page. Per plan §14
 * Phase 3: editing never PATCHes the active row — it always POSTs a new
 * `CommercialTerms` row, which the backend transactionally supersedes the
 * prior active one for (`CommercialTermsService.create`). */
export function CommercialTermsForm({
  brandId,
  agencyId,
  accessToken,
  currentTerms,
  canManage,
  onSaved,
}: CommercialTermsFormProps) {
  const { toast } = useToast();
  const [editing, setEditing] = useState(!currentTerms);
  const [form, setForm] = useState<FormState>(currentTerms ? formFromTerms(currentTerms) : emptyForm());
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    setForm(currentTerms ? formFromTerms(currentTerms) : emptyForm());
    setEditing(!currentTerms);
    setFormError(null);
  }, [currentTerms, brandId]);

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const relevantFields = BILLING_MODEL_FIELDS[form.billing_model];

  const handleSubmit = async () => {
    setFormError(null);
    setSaving(true);
    try {
      const payload: CommercialTermsCreatePayload = {
        brand_id: brandId,
        billing_model: form.billing_model,
        currency: form.currency,
        hourly_rate_cents: relevantFields.includes("hourly_rate_cents")
          ? unitsToCents(form.hourly_rate)
          : null,
        fixed_fee_cents: relevantFields.includes("fixed_fee_cents")
          ? unitsToCents(form.fixed_fee)
          : null,
        retainer_amount_cents: relevantFields.includes("retainer_amount_cents")
          ? unitsToCents(form.retainer_amount)
          : null,
        retainer_included_minutes:
          relevantFields.includes("retainer_included_minutes") && form.retainer_included_minutes.trim() !== ""
            ? Math.max(0, Number(form.retainer_included_minutes))
            : null,
        overage_rate_cents: relevantFields.includes("overage_rate_cents")
          ? unitsToCents(form.overage_rate)
          : null,
        per_item_rate_cents: relevantFields.includes("per_item_rate_cents")
          ? unitsToCents(form.per_item_rate)
          : null,
        payment_terms_days:
          form.payment_terms_days.trim() === "" ? 30 : Number(form.payment_terms_days),
        tax_rate_bps: pctToBps(form.tax_rate_pct) ?? 0,
        discount_rate_bps: pctToBps(form.discount_rate_pct),
        billing_contact_name: form.billing_contact_name.trim() || null,
        billing_contact_email: form.billing_contact_email.trim() || null,
        billing_address: form.billing_address_text.trim()
          ? { address: form.billing_address_text.trim() }
          : null,
        tax_office: form.tax_office.trim() || null,
        tax_number: form.tax_number.trim() || null,
        valid_from: form.valid_from,
        valid_until: form.valid_until.trim() || null,
      };
      const created = await financeApi.createCommercialTerms(payload, agencyId, accessToken);
      toast(
        currentTerms
          ? "Ticari koşul güncellendi (önceki koşul kapatıldı)."
          : "Ticari koşul oluşturuldu.",
        "success"
      );
      setEditing(false);
      onSaved(created);
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
          <CardTitle>Ticari Koşullar</CardTitle>
          <CardDescription>
            Bu markayla olan faturalama modeli, oranlar ve ödeme koşulları.
          </CardDescription>
        </div>
        {currentTerms && canManage && !editing && (
          <Button size="sm" variant="secondary" onClick={() => setEditing(true)}>
            <Pencil className="w-3.5 h-3.5" />
            Düzenle
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {!canManage && !currentTerms && (
          <p className="text-sm text-text-muted">
            Bu marka için henüz ticari koşul tanımlanmamış.
          </p>
        )}

        {!editing && currentTerms && (
          <div className="space-y-4">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant="accent">{BILLING_MODEL_LABEL[currentTerms.billing_model]}</Badge>
              <span className="text-xs text-text-muted">
                {BILLING_MODEL_DESCRIPTION[currentTerms.billing_model]}
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
              {currentTerms.hourly_rate_cents !== null && (
                <div>
                  <p className="text-xs text-text-muted">Saatlik Ücret</p>
                  <p className="font-medium text-text">
                    {formatMoneyCents(currentTerms.hourly_rate_cents, currentTerms.currency)}
                  </p>
                </div>
              )}
              {currentTerms.fixed_fee_cents !== null && (
                <div>
                  <p className="text-xs text-text-muted">Sabit Ücret</p>
                  <p className="font-medium text-text">
                    {formatMoneyCents(currentTerms.fixed_fee_cents, currentTerms.currency)}
                  </p>
                </div>
              )}
              {currentTerms.retainer_amount_cents !== null && (
                <div>
                  <p className="text-xs text-text-muted">Retainer Tutarı</p>
                  <p className="font-medium text-text">
                    {formatMoneyCents(currentTerms.retainer_amount_cents, currentTerms.currency)}
                  </p>
                </div>
              )}
              {currentTerms.retainer_included_minutes !== null && (
                <div>
                  <p className="text-xs text-text-muted">Dahil Süre</p>
                  <p className="font-medium text-text">
                    {(currentTerms.retainer_included_minutes / 60).toFixed(1)} sa
                  </p>
                </div>
              )}
              {currentTerms.overage_rate_cents !== null && (
                <div>
                  <p className="text-xs text-text-muted">Aşım Oranı</p>
                  <p className="font-medium text-text">
                    {formatMoneyCents(currentTerms.overage_rate_cents, currentTerms.currency)}/sa
                  </p>
                </div>
              )}
              {currentTerms.per_item_rate_cents !== null && (
                <div>
                  <p className="text-xs text-text-muted">Birim Fiyatı</p>
                  <p className="font-medium text-text">
                    {formatMoneyCents(currentTerms.per_item_rate_cents, currentTerms.currency)}
                  </p>
                </div>
              )}
              <div>
                <p className="text-xs text-text-muted">Ödeme Vadesi</p>
                <p className="font-medium text-text">{currentTerms.payment_terms_days} gün</p>
              </div>
              <div>
                <p className="text-xs text-text-muted">KDV Oranı</p>
                <p className="font-medium text-text">{(currentTerms.tax_rate_bps / 100).toFixed(1)}%</p>
              </div>
              {currentTerms.discount_rate_bps !== null && (
                <div>
                  <p className="text-xs text-text-muted">İndirim Oranı</p>
                  <p className="font-medium text-text">
                    {(currentTerms.discount_rate_bps / 100).toFixed(1)}%
                  </p>
                </div>
              )}
              <div>
                <p className="text-xs text-text-muted">Geçerlilik Başlangıcı</p>
                <p className="font-medium text-text">{formatDate(currentTerms.valid_from)}</p>
              </div>
              {currentTerms.valid_until && (
                <div>
                  <p className="text-xs text-text-muted">Geçerlilik Bitişi</p>
                  <p className="font-medium text-text">{formatDate(currentTerms.valid_until)}</p>
                </div>
              )}
            </div>

            {(currentTerms.billing_contact_name || currentTerms.billing_contact_email) && (
              <div className="pt-3 border-t border-border text-sm">
                <p className="text-xs text-text-muted mb-1">Fatura İletişim Kişisi</p>
                <p className="text-text">
                  {currentTerms.billing_contact_name}
                  {currentTerms.billing_contact_name && currentTerms.billing_contact_email && " — "}
                  {currentTerms.billing_contact_email}
                </p>
              </div>
            )}
          </div>
        )}

        {editing && canManage && (
          <div className="space-y-5">
            {!currentTerms && (
              <p className="text-sm text-text-muted">
                Bu marka için henüz ticari koşul tanımlanmamış — aşağıdan oluşturun.
              </p>
            )}
            {formError && <p className="text-sm text-danger">{formError}</p>}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Select
                label="Faturalama Modeli"
                value={form.billing_model}
                onChange={(e) => update("billing_model", e.target.value as CommercialTermsBillingModelValue)}
                options={Object.entries(BILLING_MODEL_LABEL).map(([value, label]) => ({ value, label }))}
              />
              <Select
                label="Para Birimi"
                value={form.currency}
                onChange={(e) => update("currency", e.target.value)}
                options={FINANCE_CURRENCIES.map((c) => ({ value: c, label: c }))}
              />
            </div>
            <p className="text-xs text-text-muted -mt-2">
              {BILLING_MODEL_DESCRIPTION[form.billing_model]}
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {relevantFields.includes("hourly_rate_cents") && (
                <Input
                  label={`${MONEY_FIELD_LABEL.hourly_rate_cents} (${form.currency})`}
                  type="number"
                  min={0}
                  step="0.01"
                  value={form.hourly_rate}
                  onChange={(e) => update("hourly_rate", e.target.value)}
                />
              )}
              {relevantFields.includes("fixed_fee_cents") && (
                <Input
                  label={`${MONEY_FIELD_LABEL.fixed_fee_cents} (${form.currency})`}
                  type="number"
                  min={0}
                  step="0.01"
                  value={form.fixed_fee}
                  onChange={(e) => update("fixed_fee", e.target.value)}
                />
              )}
              {relevantFields.includes("retainer_amount_cents") && (
                <Input
                  label={`${MONEY_FIELD_LABEL.retainer_amount_cents} (${form.currency})`}
                  type="number"
                  min={0}
                  step="0.01"
                  value={form.retainer_amount}
                  onChange={(e) => update("retainer_amount", e.target.value)}
                />
              )}
              {relevantFields.includes("retainer_included_minutes") && (
                <Input
                  label="Dahil Süre (dakika)"
                  type="number"
                  min={0}
                  value={form.retainer_included_minutes}
                  onChange={(e) => update("retainer_included_minutes", e.target.value)}
                  hint="ör. 2400 = 40 saat"
                />
              )}
              {relevantFields.includes("overage_rate_cents") && (
                <Input
                  label={`${MONEY_FIELD_LABEL.overage_rate_cents} (${form.currency})`}
                  type="number"
                  min={0}
                  step="0.01"
                  value={form.overage_rate}
                  onChange={(e) => update("overage_rate", e.target.value)}
                />
              )}
              {relevantFields.includes("per_item_rate_cents") && (
                <Input
                  label={`${MONEY_FIELD_LABEL.per_item_rate_cents} (${form.currency})`}
                  type="number"
                  min={0}
                  step="0.01"
                  value={form.per_item_rate}
                  onChange={(e) => update("per_item_rate", e.target.value)}
                />
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <Input
                label="Ödeme Vadesi (gün)"
                type="number"
                min={0}
                value={form.payment_terms_days}
                onChange={(e) => update("payment_terms_days", e.target.value)}
              />
              <Input
                label="KDV Oranı (%)"
                type="number"
                min={0}
                max={100}
                step="0.1"
                value={form.tax_rate_pct}
                onChange={(e) => update("tax_rate_pct", e.target.value)}
              />
              <Input
                label="İndirim Oranı (%)"
                type="number"
                min={0}
                max={100}
                step="0.1"
                value={form.discount_rate_pct}
                onChange={(e) => update("discount_rate_pct", e.target.value)}
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="Fatura İletişim Kişisi"
                value={form.billing_contact_name}
                onChange={(e) => update("billing_contact_name", e.target.value)}
              />
              <Input
                label="Fatura E-postası"
                type="email"
                value={form.billing_contact_email}
                onChange={(e) => update("billing_contact_email", e.target.value)}
              />
              <Input
                label="Vergi Dairesi"
                value={form.tax_office}
                onChange={(e) => update("tax_office", e.target.value)}
              />
              <Input
                label="Vergi Numarası"
                value={form.tax_number}
                onChange={(e) => update("tax_number", e.target.value)}
              />
            </div>

            <Input
              label="Fatura Adresi"
              value={form.billing_address_text}
              onChange={(e) => update("billing_address_text", e.target.value)}
            />

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="Geçerlilik Başlangıcı"
                type="date"
                value={form.valid_from}
                onChange={(e) => update("valid_from", e.target.value)}
              />
              <Input
                label="Geçerlilik Bitişi (opsiyonel)"
                type="date"
                value={form.valid_until}
                onChange={(e) => update("valid_until", e.target.value)}
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              {currentTerms && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setForm(formFromTerms(currentTerms));
                    setEditing(false);
                    setFormError(null);
                  }}
                >
                  Vazgeç
                </Button>
              )}
              <Button size="sm" onClick={handleSubmit} isLoading={saving}>
                {currentTerms ? "Yeni Koşul Olarak Kaydet" : "Ticari Koşul Oluştur"}
              </Button>
            </div>
          </div>
        )}

        {!editing && !currentTerms && canManage && (
          <div className="text-center py-8">
            <p className="text-sm text-text-muted mb-4">
              Bu marka için henüz ticari koşul tanımlanmamış.
            </p>
            <Button size="sm" onClick={() => setEditing(true)}>
              Ticari Koşul Oluştur
            </Button>
          </div>
        )}

        {!canManage && currentTerms && (
          <div className="flex items-center gap-2 mt-4 text-xs text-text-muted">
            <Lock className="w-3.5 h-3.5" />
            Ticari koşulları düzenleme yetkiniz yok — yalnızca görüntülüyorsunuz.
          </div>
        )}
      </CardContent>
    </Card>
  );
}

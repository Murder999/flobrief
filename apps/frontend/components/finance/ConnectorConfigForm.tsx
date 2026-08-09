"use client";

import { Button } from "@/components/ui/button";
import { Drawer } from "@/components/ui/drawer";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import {
  ApiError,
  financeApi,
  type AccountingConnectorRead,
  type AccountingProviderValue,
} from "@/lib/api-client";
import { ACCOUNTING_PROVIDER_LABEL, REAL_ACCOUNTING_PROVIDERS } from "@/lib/finance";
import { Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

interface ConnectorConfigFormProps {
  isOpen: boolean;
  onClose: () => void;
  agencyId: string;
  accessToken: string;
  /** null = create mode. */
  connector: AccountingConnectorRead | null;
  onSaved: (connector: AccountingConnectorRead) => void;
}

interface CredentialRow {
  key: string;
  value: string;
}

function emptyRows(): CredentialRow[] {
  return [{ key: "", value: "" }];
}

function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.detail === "string") return e.detail;
    return e.message;
  }
  return e instanceof Error ? e.message : "Kaydedilemedi";
}

const PROVIDER_OPTIONS = (Object.entries(ACCOUNTING_PROVIDER_LABEL) as [AccountingProviderValue, string][]).map(
  ([value, label]) => ({
    value,
    label: REAL_ACCOUNTING_PROVIDERS.has(value) ? label : `${label} (Yakında)`,
    disabled: !REAL_ACCOUNTING_PROVIDERS.has(value),
  })
);

/** Create/edit drawer for an `AccountingConnector`. Every provider except
 * "manual" is disabled in the dropdown (native `<option disabled>`, plan
 * §10/§12) — the backend accepts the enum value but any real dispatch on
 * it raises 501, so the UI never lets a user pick one and believe it will
 * work. Credential rows are write-only: never pre-filled from a
 * `connector` prop (the backend never returns credentials to pre-fill
 * from — there is nothing to accidentally render), and cleared from
 * component state immediately after a successful save so a submitted
 * secret does not linger in memory/React DevTools longer than necessary.
 * An empty row set on submit sends no `credentials` key at all (never an
 * empty object) — the backend's `update()` treats a present-but-empty
 * value as "clear the secret", so omission is the only safe way to mean
 * "leave unchanged" on edit. */
export function ConnectorConfigForm({
  isOpen,
  onClose,
  agencyId,
  accessToken,
  connector,
  onSaved,
}: ConnectorConfigFormProps) {
  const { toast } = useToast();
  const isEdit = !!connector;
  const [provider, setProvider] = useState<AccountingProviderValue>("manual");
  const [rows, setRows] = useState<CredentialRow[]>(emptyRows());
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    setProvider(connector?.provider ?? "manual");
    setRows(emptyRows());
    setFormError(null);
  }, [isOpen, connector]);

  const updateRow = (index: number, field: "key" | "value", value: string) =>
    setRows((prev) => prev.map((r, i) => (i === index ? { ...r, [field]: value } : r)));

  const addRow = () => setRows((prev) => [...prev, { key: "", value: "" }]);

  const removeRow = (index: number) =>
    setRows((prev) => (prev.length === 1 ? emptyRows() : prev.filter((_, i) => i !== index)));

  const buildCredentials = (): Record<string, string> | undefined => {
    const filled = rows.filter((r) => r.key.trim() !== "");
    if (filled.length === 0) return undefined;
    const result: Record<string, string> = {};
    for (const r of filled) result[r.key.trim()] = r.value;
    return result;
  };

  const handleSubmit = async () => {
    if (!REAL_ACCOUNTING_PROVIDERS.has(provider)) {
      setFormError('Bu sağlayıcı henüz desteklenmiyor. Lütfen "Manuel" seçin.');
      return;
    }
    setFormError(null);
    setSaving(true);
    try {
      const credentials = buildCredentials();
      const saved =
        isEdit && connector
          ? await financeApi.updateConnector(connector.id, { credentials }, agencyId, accessToken)
          : await financeApi.createConnector({ provider, credentials }, agencyId, accessToken);

      setRows(emptyRows());
      toast(isEdit ? "Bağlantı güncellendi." : "Bağlantı oluşturuldu.", "success");
      onSaved(saved);
      onClose();
    } catch (e) {
      const message = errorMessage(e);
      setFormError(message);
      toast(message, "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Drawer
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? "Bağlantıyı Düzenle" : "Bağlantı Ekle"}
      description="Muhasebe entegrasyonu yapılandırması"
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={onClose}>
            Vazgeç
          </Button>
          <Button size="sm" onClick={handleSubmit} isLoading={saving}>
            {isEdit ? "Kaydet" : "Bağlantıyı Oluştur"}
          </Button>
        </>
      }
    >
      <div className="space-y-5">
        {formError && <p className="text-sm text-danger">{formError}</p>}

        {isEdit ? (
          <div>
            <p className="text-xs font-medium text-text-muted tracking-wide mb-1.5">Sağlayıcı</p>
            <p className="text-sm text-text">{ACCOUNTING_PROVIDER_LABEL[provider]}</p>
          </div>
        ) : (
          <Select
            label="Sağlayıcı"
            value={provider}
            onChange={(e) => setProvider(e.target.value as AccountingProviderValue)}
            options={PROVIDER_OPTIONS}
          />
        )}

        {!REAL_ACCOUNTING_PROVIDERS.has(provider) && (
          <p className="text-xs text-warning bg-warning/10 border border-warning/20 rounded-lg px-3 py-2">
            Bu sağlayıcı yakında kullanıma sunulacak. Şu an yalnızca &ldquo;Manuel&rdquo;
            bağlantı tipi çalışır.
          </p>
        )}

        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-medium text-text-muted tracking-wide">
              Kimlik Bilgileri (opsiyonel)
            </p>
            <button
              type="button"
              onClick={addRow}
              className="text-xs text-accent hover:underline inline-flex items-center gap-1"
            >
              <Plus className="w-3 h-3" />
              Satır Ekle
            </button>
          </div>
          <p className="text-xs text-text-muted mb-3">
            &ldquo;Manuel&rdquo; bağlantı için kimlik bilgisi gerekmez — bu alan yalnızca
            gelecekteki sağlayıcı entegrasyonları için hazırlıktır. Girilen değerler yalnızca
            kaydedilir, hiçbir zaman geri gösterilmez.
          </p>
          <div className="space-y-2">
            {rows.map((row, i) => (
              <div key={i} className="flex items-center gap-2">
                <Input
                  placeholder="anahtar"
                  value={row.key}
                  onChange={(e) => updateRow(i, "key", e.target.value)}
                  className="flex-1"
                />
                <Input
                  placeholder="değer"
                  type="password"
                  autoComplete="off"
                  value={row.value}
                  onChange={(e) => updateRow(i, "value", e.target.value)}
                  className="flex-1"
                />
                <button
                  type="button"
                  onClick={() => removeRow(i)}
                  className="text-text-muted hover:text-danger transition-colors flex-shrink-0"
                  aria-label="Satırı kaldır"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Drawer>
  );
}

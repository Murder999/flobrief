"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import {
  whatsappPreferencesApi,
  whatsappTestSendApi,
  type WhatsAppEventPreferenceRead,
  type WhatsAppTenantTestSendResponse,
  type WhatsAppUserStatusRead,
} from "@/lib/api-client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

interface WhatsAppPreferencesPanelProps {
  accessToken: string | null;
  /** Agency id for agency-portal callers; null for brand-portal callers
   * (the brand-portal test-send route needs no X-Agency-ID header). */
  agencyId: string | null;
  portal: "agency" | "brand";
  phoneSettingsHref: string;
}

const GROUP_ORDER = [
  "brief_and_work",
  "comments_and_collaboration",
  "delivery_and_approval",
  "finance",
];

function StatusDot({ tone }: { tone: "ok" | "warn" | "off" }) {
  const cls =
    tone === "ok" ? "bg-emerald-400" : tone === "warn" ? "bg-amber-400" : "bg-text-muted/40";
  return <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${cls}`} />;
}

function Skeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="h-24 bg-surface-2 rounded-xl border border-border" />
      <div className="h-16 bg-surface-2 rounded-xl border border-border" />
      {[1, 2, 3].map((i) => (
        <div key={i} className="h-40 bg-surface-2 rounded-xl border border-border" />
      ))}
    </div>
  );
}

function Toggle({
  checked,
  disabled,
  onChange,
  label,
}: {
  checked: boolean;
  disabled?: boolean;
  onChange: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={onChange}
      className={`relative inline-flex h-6 w-11 min-w-[44px] min-h-[24px] items-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:opacity-40 flex-shrink-0 ${
        checked && !disabled ? "bg-emerald-500" : "bg-surface-2 border border-border"
      }`}
    >
      <span
        className={`inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform ${
          checked && !disabled ? "translate-x-6" : "translate-x-1"
        }`}
      />
    </button>
  );
}

export function WhatsAppPreferencesPanel({
  accessToken,
  agencyId,
  portal,
  phoneSettingsHref,
}: WhatsAppPreferencesPanelProps) {
  const [status, setStatus] = useState<WhatsAppUserStatusRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [consentModalOpen, setConsentModalOpen] = useState(false);
  const [consentSubmitting, setConsentSubmitting] = useState(false);
  const [togglingEvent, setTogglingEvent] = useState<string | null>(null);
  const [testSending, setTestSending] = useState(false);
  const [testResult, setTestResult] = useState<WhatsAppTenantTestSendResponse | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!accessToken) return;
    setLoading(true);
    setLoadError(null);
    whatsappPreferencesApi
      .getStatus(agencyId, accessToken)
      .then(setStatus)
      .catch(() => setLoadError("WhatsApp durumu yüklenemedi."))
      .finally(() => setLoading(false));
  }, [accessToken, agencyId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleOptIn = async () => {
    if (!accessToken) return;
    setConsentSubmitting(true);
    setActionError(null);
    try {
      const updated = await whatsappPreferencesApi.updateConsent(true, agencyId, accessToken);
      setStatus(updated);
      setConsentModalOpen(false);
    } catch {
      setActionError("Onay kaydedilemedi. Lütfen tekrar deneyin.");
    } finally {
      setConsentSubmitting(false);
    }
  };

  const handleOptOut = async () => {
    if (!accessToken) return;
    setConsentSubmitting(true);
    setActionError(null);
    try {
      const updated = await whatsappPreferencesApi.updateConsent(false, agencyId, accessToken);
      setStatus(updated);
    } catch {
      setActionError("İşlem tamamlanamadı. Lütfen tekrar deneyin.");
    } finally {
      setConsentSubmitting(false);
    }
  };

  const handleEventToggle = async (event: WhatsAppEventPreferenceRead) => {
    if (!accessToken) return;
    setTogglingEvent(event.event_type);
    setActionError(null);
    try {
      const updated = await whatsappPreferencesApi.updateEventPreference(
        event.event_type,
        !event.whatsapp_enabled,
        agencyId,
        accessToken
      );
      setStatus((prev) =>
        prev
          ? {
              ...prev,
              events: prev.events.map((e) => (e.event_type === updated.event_type ? updated : e)),
            }
          : prev
      );
    } catch {
      setActionError("Tercih kaydedilemedi. Lütfen tekrar deneyin.");
    } finally {
      setTogglingEvent(null);
    }
  };

  const handleTestSend = async () => {
    if (!accessToken) return;
    setTestSending(true);
    setTestResult(null);
    try {
      const result =
        portal === "brand"
          ? await whatsappPreferencesApi.testSendBrand(accessToken)
          : agencyId
          ? await whatsappTestSendApi.testSend(agencyId, accessToken)
          : null;
      if (result) setTestResult(result);
      load();
    } catch (e: unknown) {
      const err = e as { message?: string };
      setTestResult({
        delivery_id: null,
        masked_recipient: null,
        status: "failed",
        provider: "unknown",
        template_key: "",
        provider_message_id: null,
        safe_error: err?.message ?? "Test mesajı gönderilemedi.",
      });
    } finally {
      setTestSending(false);
    }
  };

  if (loading) return <Skeleton />;
  if (loadError || !status) {
    return (
      <div className="px-4 py-3 bg-danger/10 border border-danger/30 rounded-xl text-sm text-danger flex items-center justify-between gap-3">
        <span>{loadError ?? "WhatsApp durumu yüklenemedi."}</span>
        <button onClick={load} className="text-xs underline underline-offset-2 flex-shrink-0">
          Tekrar dene
        </button>
      </div>
    );
  }

  const { phone, consent, master_enabled, whatsapp_provider_active, events, is_demo_tenant } =
    status;

  const canOptIn = whatsapp_provider_active && phone.has_phone_number;
  const readyForTest = master_enabled && consent.whatsapp_opt_in && phone.has_phone_number;

  const groups = GROUP_ORDER.map((key) => ({
    key,
    label: events.find((e) => e.group === key)?.group_label ?? key,
    events: events.filter((e) => e.group === key),
  })).filter((g) => g.events.length > 0);

  return (
    <div className="space-y-5">
      {/* Provider not active */}
      {!whatsapp_provider_active && (
        <div className="flex gap-3 bg-surface-2 border border-border rounded-xl px-5 py-4">
          <svg className="w-4 h-4 text-text-muted flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-xs text-text-muted leading-relaxed">
            WhatsApp sağlayıcısı platform yöneticisi tarafından henüz yapılandırılmamış.
            Yapılandırıldığında bu bölüm otomatik olarak etkinleşecektir.
          </p>
        </div>
      )}

      {is_demo_tenant && (
        <div className="flex gap-3 bg-accent/5 border border-accent/20 rounded-xl px-5 py-4">
          <p className="text-xs text-text-muted leading-relaxed">
            Bu demo ortamda gerçek WhatsApp mesajı gönderilmez. Tüm tercihler ve test akışı
            görüntülenebilir, ancak gönderim daima simüle edilmiş şekilde işaretlenir.
          </p>
        </div>
      )}

      {/* Master toggle card */}
      <div className="bg-surface border border-border rounded-xl px-6 py-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-text">WhatsApp Bildirimleri</h3>
              <Badge variant={master_enabled ? "success" : "default"}>
                {master_enabled ? "Açık" : "Kapalı"}
              </Badge>
            </div>
            <p className="text-xs text-text-muted mt-1 leading-relaxed max-w-md">
              Açık olduğunda, aşağıda seçtiğiniz bildirim türleri onaylı WhatsApp şablonları
              üzerinden telefonunuza iletilir. İstediğiniz zaman kapatabilirsiniz.
            </p>
          </div>
          <Toggle
            checked={master_enabled}
            disabled={!canOptIn && !master_enabled}
            label="WhatsApp bildirimlerini aç/kapat"
            onChange={() => (master_enabled ? handleOptOut() : setConsentModalOpen(true))}
          />
        </div>

        <div className="mt-4 pt-4 border-t border-border grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="flex items-center gap-2 text-xs">
            <StatusDot tone={phone.has_phone_number ? "ok" : "warn"} />
            <span className="text-text-muted">Telefon:</span>
            {phone.has_phone_number ? (
              <span className="font-mono text-text">{phone.phone_masked}</span>
            ) : (
              <Link href={phoneSettingsHref} className="text-accent hover:underline">
                Telefon ekle
              </Link>
            )}
            {phone.has_phone_number && !phone.phone_verified && (
              <span className="text-text-muted/70">(doğrulanmamış)</span>
            )}
          </div>
          <div className="flex items-center gap-2 text-xs">
            <StatusDot tone={consent.whatsapp_opt_in ? "ok" : "off"} />
            <span className="text-text-muted">Onay:</span>
            <span className="text-text">
              {consent.whatsapp_opt_in && consent.whatsapp_opt_in_at
                ? `Verildi — ${new Date(consent.whatsapp_opt_in_at).toLocaleDateString("tr-TR")}`
                : consent.whatsapp_opt_out_at
                ? `Kapatıldı — ${new Date(consent.whatsapp_opt_out_at).toLocaleDateString("tr-TR")}`
                : "Henüz verilmedi"}
            </span>
          </div>
        </div>
      </div>

      {actionError && (
        <div className="px-4 py-2.5 bg-danger/10 border border-danger/30 rounded-lg text-xs text-danger">
          {actionError}
        </div>
      )}

      {/* Event groups */}
      {master_enabled && groups.length > 0 && (
        <div className="space-y-4">
          {groups.map((group) => (
            <div key={group.key} className="bg-surface border border-border rounded-xl overflow-hidden">
              <div className="px-5 py-3 bg-surface-2/50 border-b border-border">
                <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wide">
                  {group.label}
                </h4>
              </div>
              <div className="divide-y divide-border">
                {group.events.map((event) => (
                  <div
                    key={event.event_type}
                    className="flex items-center justify-between gap-4 px-5 py-3.5"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-text truncate">{event.event_label}</p>
                      {!event.template_ready && (
                        <p className="text-[11px] text-amber-400 mt-0.5">
                          Şablon henüz hazır değil — açık olsa da şu an gönderim yapılamıyor.
                        </p>
                      )}
                    </div>
                    <Toggle
                      checked={event.whatsapp_enabled}
                      disabled={togglingEvent === event.event_type}
                      label={event.event_label}
                      onChange={() => handleEventToggle(event)}
                    />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Test send + last delivery */}
      <div className="bg-surface border border-border rounded-xl px-5 py-4">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <p className="text-sm font-medium text-text">Test mesajı gönder</p>
            <p className="text-xs text-text-muted mt-0.5">
              Kayıtlı telefon numaranıza kontrollü bir WhatsApp test mesajı gönderilir.
            </p>
          </div>
          <Button
            variant="secondary"
            size="sm"
            disabled={testSending || !readyForTest}
            onClick={handleTestSend}
          >
            {testSending ? "Gönderiliyor…" : "Test Mesajı Gönder"}
          </Button>
        </div>
        {!readyForTest && (
          <p className="text-xs text-text-muted mt-2">
            Test göndermek için WhatsApp&apos;ı açın, telefon numaranızı ekleyin ve onay verin.
          </p>
        )}
        {testResult && (
          <div className="mt-3 p-3 bg-surface-2 border border-border rounded-lg text-xs space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="text-text-muted w-20">Durum</span>
              <code className="font-mono px-2 py-0.5 rounded border bg-surface text-text border-border">
                {testResult.status}
              </code>
            </div>
            {testResult.masked_recipient && (
              <div className="flex items-center gap-2">
                <span className="text-text-muted w-20">Alıcı</span>
                <code className="font-mono text-text">{testResult.masked_recipient}</code>
              </div>
            )}
            {testResult.safe_error && (
              <div className="flex items-start gap-2">
                <span className="text-text-muted w-20 flex-shrink-0">Not</span>
                <span className="text-text-muted">{testResult.safe_error}</span>
              </div>
            )}
          </div>
        )}
        {status.last_delivery_status && (
          <p className="mt-3 text-[11px] text-text-muted">
            Son WhatsApp bildirimi: <span className="font-mono">{status.last_delivery_status}</span>
            {status.last_delivery_at &&
              ` — ${new Date(status.last_delivery_at).toLocaleString("tr-TR")}`}
          </p>
        )}
      </div>

      <Modal
        isOpen={consentModalOpen}
        onClose={() => setConsentModalOpen(false)}
        title="WhatsApp Bildirim Onayı"
        maxWidth="sm"
      >
        <div className="space-y-4">
          <p className="text-sm text-text-secondary leading-relaxed">
            WhatsApp bildirimlerini açtığınızda, size atanan brief&apos;ler, yorumlar, onay talepleri ve
            faturalarla ilgili seçtiğiniz bildirim türleri kayıtlı telefon numaranıza
            gönderilecektir.
          </p>
          <ul className="text-xs text-text-muted space-y-1.5 list-disc list-inside">
            <li>İstediğiniz zaman bu ayarı kapatabilirsiniz.</li>
            <li>Telefon numaranız yalnızca bildirim göndermek için kullanılır.</li>
            <li>Demo ortamlarda gerçek bir mesaj gönderilmez.</li>
          </ul>
          {actionError && <p className="text-xs text-danger">{actionError}</p>}
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="ghost" size="sm" onClick={() => setConsentModalOpen(false)}>
              Vazgeç
            </Button>
            <Button variant="primary" size="sm" isLoading={consentSubmitting} onClick={handleOptIn}>
              Onaylıyorum, Aç
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

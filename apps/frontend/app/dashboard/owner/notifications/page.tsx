"use client";

import { WhatsAppOwnerCenter } from "@/components/notifications/WhatsAppOwnerCenter";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import {
  twilioProviderApi,
  type TwilioProviderStatusRead,
  type TwilioProviderUpdate,
  type WhatsAppProviderType,
} from "@/lib/api-client";
import { useEffect, useState } from "react";

// ── Types ─────────────────────────────────────────────────────────────────────

type Tab = "settings" | "test" | "guide";

// ── Helpers ───────────────────────────────────────────────────────────────────

function StatusBadge({ configured, enabled }: { configured: boolean; enabled: boolean }) {
  if (!configured) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border bg-surface-2 text-text-muted border-border">
        <span className="w-1.5 h-1.5 rounded-full bg-text-muted/40" />
        Yapılandırılmamış
      </span>
    );
  }
  if (!enabled) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border bg-amber-500/10 text-amber-400 border-amber-500/20">
        <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
        Devre Dışı
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border bg-emerald-500/10 text-emerald-400 border-emerald-500/20">
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
      Aktif
    </span>
  );
}

// ── SecretField ───────────────────────────────────────────────────────────────

interface SecretFieldProps {
  label: string;
  isSet: boolean;
  maskedValue?: string | null;
  newValue: string;
  editing: boolean;
  onEdit: () => void;
  onCancelEdit: () => void;
  onChange: (v: string) => void;
  onClear?: () => void;
  placeholder?: string;
  hint?: string;
  optional?: boolean;
}

function SecretField({
  label,
  isSet,
  maskedValue,
  newValue,
  editing,
  onEdit,
  onCancelEdit,
  onChange,
  onClear,
  placeholder,
  hint,
  optional,
}: SecretFieldProps) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-1.5">
        <label className="text-xs font-medium text-text-muted">{label}</label>
        {optional && (
          <span className="text-[10px] text-text-muted/50 border border-border rounded px-1">
            opsiyonel
          </span>
        )}
      </div>

      {editing ? (
        <div className="flex gap-2">
          <input
            type="password"
            value={newValue}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder ?? "Yeni değer girin"}
            autoComplete="new-password"
            className="flex-1 bg-surface-2 border border-accent/40 rounded-lg px-3 py-2 text-sm text-text placeholder:text-text-muted/50 focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20 font-mono"
          />
          <button
            type="button"
            onClick={onCancelEdit}
            className="px-3 py-2 text-xs text-text-muted border border-border rounded-lg hover:bg-surface-2 transition-colors"
          >
            İptal
          </button>
        </div>
      ) : isSet ? (
        <div className="flex items-center gap-2">
          <div className="flex-1 bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text-muted font-mono">
            {maskedValue ?? "••••••••••••"}
          </div>
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex-shrink-0">
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            Kayıtlı
          </span>
          <button
            type="button"
            onClick={onEdit}
            className="text-xs text-accent hover:text-accent/80 transition-colors px-2 py-1 flex-shrink-0"
          >
            Değiştir
          </button>
          {onClear && (
            <button
              type="button"
              onClick={onClear}
              className="text-xs text-red-400/70 hover:text-red-400 transition-colors px-2 py-1 flex-shrink-0"
            >
              Sil
            </button>
          )}
        </div>
      ) : (
        <button
          type="button"
          onClick={onEdit}
          className="w-full bg-surface-2 border border-dashed border-border rounded-lg px-3 py-2.5 text-sm text-text-muted text-left hover:border-accent/30 hover:text-text transition-colors flex items-center gap-2"
        >
          <svg className="w-3.5 h-3.5 text-text-muted/50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          {optional ? "Ayarlamak için tıklayın (opsiyonel)" : "Ayarlamak için tıklayın"}
        </button>
      )}

      {hint && <p className="mt-1.5 text-xs text-text-muted/60">{hint}</p>}
    </div>
  );
}

// ── Provider type options ─────────────────────────────────────────────────────

const PROVIDER_TYPES: { value: WhatsAppProviderType; label: string; desc: string }[] = [
  { value: "disabled", label: "Devre Dışı", desc: "WhatsApp gönderimi kapalı" },
  { value: "twilio_sandbox", label: "Twilio Sandbox", desc: "Geliştirme ve test için" },
  { value: "twilio_production", label: "Twilio Production", desc: "Canlı Business hesabı" },
];

// ── Test result badge ─────────────────────────────────────────────────────────

function TestResultBadge({ status }: { status: string }) {
  if (status === "sent") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded text-xs font-mono">
        ✓ sent
      </span>
    );
  }
  if (status === "not_configured") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-surface-2 text-text-muted border border-border rounded text-xs font-mono">
        not_configured
      </span>
    );
  }
  if (status === "skipped" || status.startsWith("skipped")) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-500/10 text-amber-400 border border-amber-500/20 rounded text-xs font-mono">
        {status}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-red-500/10 text-red-400 border border-red-500/20 rounded text-xs font-mono">
      ✗ {status}
    </span>
  );
}


// ── Main Component ────────────────────────────────────────────────────────────

export default function OwnerNotificationsPage() {
  const { user, accessToken } = useAuth();
  const { activeAgency } = useWorkspace();

  const isPlatformAdmin = user?.user_type === "platform_admin";
  const isAgencyOwner =
    activeAgency?.member_role === "owner" || activeAgency?.member_role === "admin";

  const [activeTab, setActiveTab] = useState<Tab>("settings");
  const [status, setStatus] = useState<TwilioProviderStatusRead | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Form fields (only used when editing)
  const [providerType, setProviderType] = useState<WhatsAppProviderType>("disabled");
  const [isEnabled, setIsEnabled] = useState(false);

  const [accountSid, setAccountSid] = useState("");
  const [editingSid, setEditingSid] = useState(false);

  const [authToken, setAuthToken] = useState("");
  const [editingToken, setEditingToken] = useState(false);

  const [whatsappFrom, setWhatsappFrom] = useState("");
  const [editingFrom, setEditingFrom] = useState(false);

  const [messagingSid, setMessagingSid] = useState("");
  const [editingMsid, setEditingMsid] = useState(false);

  const [webhookToken, setWebhookToken] = useState("");
  const [editingWebhook, setEditingWebhook] = useState(false);

  // Test send
  const [testPhone, setTestPhone] = useState("");
  const [testMessage, setTestMessage] = useState("");
  const [testSending, setTestSending] = useState(false);
  const [testResult, setTestResult] = useState<{
    status: string;
    provider: string;
    provider_message_id: string | null;
    error_message: string | null;
    to_phone_masked: string;
  } | null>(null);

  const applyStatus = (data: TwilioProviderStatusRead) => {
    setStatus(data);
    setProviderType(data.provider_type as WhatsAppProviderType);
    setIsEnabled(data.is_enabled);
  };

  const loadStatus = async () => {
    if (!accessToken || !isPlatformAdmin) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const data = await twilioProviderApi.getStatus(accessToken);
      applyStatus(data);
    } catch (e: unknown) {
      const err = e as { message?: string };
      setLoadError(err?.message ?? "Twilio ayarları yüklenemedi.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, isPlatformAdmin]);

  const handleSave = async () => {
    if (!accessToken) return;
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(false);

    const update: TwilioProviderUpdate = {
      provider_type: providerType,
      is_enabled: isEnabled,
    };

    if (editingSid && accountSid.trim()) update.account_sid = accountSid.trim();
    if (editingToken && authToken.trim()) update.auth_token = authToken.trim();
    if (editingFrom && whatsappFrom.trim()) update.whatsapp_from = whatsappFrom.trim();
    if (editingMsid && messagingSid.trim()) update.messaging_service_sid = messagingSid.trim();
    if (editingWebhook && webhookToken.trim()) update.webhook_verify_token = webhookToken.trim();

    try {
      const updated = await twilioProviderApi.update(update, accessToken);
      applyStatus(updated);
      setEditingSid(false); setAccountSid("");
      setEditingToken(false); setAuthToken("");
      setEditingFrom(false); setWhatsappFrom("");
      setEditingMsid(false); setMessagingSid("");
      setEditingWebhook(false); setWebhookToken("");
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 4000);
    } catch (e: unknown) {
      const err = e as { message?: string };
      setSaveError(err?.message ?? "Kaydedilemedi.");
    } finally {
      setSaving(false);
    }
  };

  const handleClearSecret = async (
    field: "auth_token" | "account_sid" | "whatsapp_from" | "messaging_service_sid" | "webhook_verify_token"
  ) => {
    if (!accessToken) return;
    if (!confirm("Bu secret kalıcı olarak silinecek. Emin misiniz?")) return;
    try {
      const updated = await twilioProviderApi.clearSecret(field, accessToken);
      applyStatus(updated);
    } catch (e: unknown) {
      const err = e as { message?: string };
      alert(err?.message ?? "Secret silinemedi.");
    }
  };

  const handleTestSend = async () => {
    if (!accessToken || !testPhone.trim()) return;
    setTestSending(true);
    setTestResult(null);
    try {
      const result = await twilioProviderApi.testSend(
        { to_phone: testPhone.trim(), message: testMessage.trim() || undefined },
        accessToken
      );
      setTestResult(result);
    } catch (e: unknown) {
      const err = e as { message?: string };
      setTestResult({
        status: "failed",
        provider: "unknown",
        provider_message_id: null,
        error_message: err?.message ?? "Test gönderilemedi.",
        to_phone_masked: "***",
      });
    } finally {
      setTestSending(false);
    }
  };

  // ── Agency owner view ───────────────────────────────────────────────────────

  if (!isPlatformAdmin && isAgencyOwner) {
    return (
      <div className="p-8 max-w-5xl mx-auto">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-text">WhatsApp Yönetim Merkezi</h1>
          <p className="text-sm text-text-muted mt-1">
            Bağlantı durumu, şablon hazırlığı ve kullanıcı katılımı özetini aşağıda bulabilirsiniz.
          </p>
        </div>
        <WhatsAppOwnerCenter />
      </div>
    );
  }

  // ── Platform admin view ─────────────────────────────────────────────────────

  const TABS: { id: Tab; label: string }[] = [
    { id: "settings", label: "Ayarlar" },
    { id: "test", label: "Test Mesajı" },
    { id: "guide", label: "Kurulum Rehberi" },
  ];

  return (
    <div className="p-8 max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-text">WhatsApp Bildirim Ayarları</h1>
        <p className="text-sm text-text-muted mt-1">
          Twilio WhatsApp entegrasyonu için provider ayarları.
        </p>
      </div>

      {/* Status bar */}
      {!loading && status && (
        <div className="bg-surface border border-border rounded-xl px-5 py-4 mb-6 flex items-center gap-4">
          <StatusBadge configured={status.is_configured} enabled={status.is_enabled} />
          <div className="flex-1 flex items-center gap-6 text-xs text-text-muted">
            {status.account_sid_masked && (
              <span>SID: <code className="font-mono text-text">{status.account_sid_masked}</code></span>
            )}
            {status.whatsapp_from_masked && (
              <span>From: <code className="font-mono text-text">{status.whatsapp_from_masked}</code></span>
            )}
            {status.configured_at && (
              <span>Son güncelleme: {new Date(status.configured_at).toLocaleString("tr-TR")}</span>
            )}
          </div>
          {(status.missing_fields?.length ?? 0) > 0 && (
            <span className="text-xs text-amber-400">
              Eksik: {status.missing_fields.join(", ")}
            </span>
          )}
        </div>
      )}

      {/* Load error */}
      {loadError && (
        <div className="mb-6 px-4 py-3 bg-red-500/5 border border-red-500/20 rounded-xl text-sm text-red-400 flex items-center gap-3">
          <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <span>{loadError}</span>
          <button
            onClick={loadStatus}
            className="ml-auto text-xs text-accent hover:underline"
          >
            Tekrar dene
          </button>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="bg-surface border border-border rounded-xl p-6 mb-6 animate-pulse">
          <div className="h-4 bg-surface-2 rounded w-48 mb-4" />
          <div className="space-y-3">
            {[1, 2, 3].map((i) => <div key={i} className="h-10 bg-surface-2 rounded-lg" />)}
          </div>
        </div>
      )}

      {/* Tabs */}
      {!loading && (
        <>
          <div className="flex gap-1 bg-surface-2 p-1 rounded-xl mb-6">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all ${
                  activeTab === tab.id
                    ? "bg-surface text-text shadow-sm border border-border"
                    : "text-text-muted hover:text-text"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* ── Tab: Ayarlar ────────────────────────────────────────── */}
          {activeTab === "settings" && (
            <div className="space-y-6">
              {/* Provider type + enable toggle */}
              <div className="bg-surface border border-border rounded-xl p-5">
                <h2 className="text-sm font-semibold text-text mb-4">Sağlayıcı Yapılandırması</h2>

                <div className="mb-4">
                  <label className="block text-xs font-medium text-text-muted mb-1.5">
                    WhatsApp Sağlayıcısı
                  </label>
                  <select
                    value={providerType}
                    onChange={(e) => setProviderType(e.target.value as WhatsAppProviderType)}
                    className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20"
                  >
                    {PROVIDER_TYPES.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label} — {o.desc}
                      </option>
                    ))}
                  </select>
                </div>

                <div
                  className="flex items-center gap-3 p-3 bg-surface-2 rounded-lg cursor-pointer"
                  onClick={() => setIsEnabled(!isEnabled)}
                >
                  <button
                    type="button"
                    className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors flex-shrink-0 ${
                      isEnabled ? "bg-accent" : "bg-border"
                    }`}
                  >
                    <span
                      className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${
                        isEnabled ? "translate-x-4" : "translate-x-0.5"
                      }`}
                    />
                  </button>
                  <div>
                    <p className="text-sm font-medium text-text">WhatsApp Bildirimleri</p>
                    <p className="text-xs text-text-muted">
                      {isEnabled ? "Aktif — mesajlar gönderilecek" : "Devre dışı — mesajlar gönderilmeyecek"}
                    </p>
                  </div>
                </div>
              </div>

              {/* Twilio credentials */}
              <div className="bg-surface border border-border rounded-xl p-5">
                <h2 className="text-sm font-semibold text-text mb-4">Twilio Kimlik Bilgileri</h2>
                <div className="space-y-4">
                  <SecretField
                    label="Account SID"
                    isSet={!!status?.account_sid_masked}
                    maskedValue={status?.account_sid_masked}
                    newValue={accountSid}
                    editing={editingSid}
                    onEdit={() => setEditingSid(true)}
                    onCancelEdit={() => { setEditingSid(false); setAccountSid(""); }}
                    onChange={setAccountSid}
                    onClear={status?.account_sid_masked ? () => handleClearSecret("account_sid") : undefined}
                    placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                    hint="Twilio Console → Account Info → Account SID"
                  />

                  <SecretField
                    label="Auth Token"
                    isSet={status?.auth_token_set ?? false}
                    maskedValue={null}
                    newValue={authToken}
                    editing={editingToken}
                    onEdit={() => setEditingToken(true)}
                    onCancelEdit={() => { setEditingToken(false); setAuthToken(""); }}
                    onChange={setAuthToken}
                    onClear={status?.auth_token_set ? () => handleClearSecret("auth_token") : undefined}
                    placeholder="Auth token girin"
                    hint="Hiçbir zaman geri döndürülmez. Kaydediliyse 'Kayıtlı' gösterilir."
                  />

                  <SecretField
                    label="WhatsApp From"
                    isSet={!!status?.whatsapp_from_masked}
                    maskedValue={status?.whatsapp_from_masked}
                    newValue={whatsappFrom}
                    editing={editingFrom}
                    onEdit={() => setEditingFrom(true)}
                    onCancelEdit={() => { setEditingFrom(false); setWhatsappFrom(""); }}
                    onChange={setWhatsappFrom}
                    onClear={status?.whatsapp_from_masked ? () => handleClearSecret("whatsapp_from") : undefined}
                    placeholder="whatsapp:+14155238886"
                    hint="Sandbox için: whatsapp:+14155238886"
                  />

                  <SecretField
                    label="Messaging Service SID"
                    isSet={status?.messaging_service_sid_set ?? false}
                    maskedValue={null}
                    newValue={messagingSid}
                    editing={editingMsid}
                    onEdit={() => setEditingMsid(true)}
                    onCancelEdit={() => { setEditingMsid(false); setMessagingSid(""); }}
                    onChange={setMessagingSid}
                    onClear={status?.messaging_service_sid_set ? () => handleClearSecret("messaging_service_sid") : undefined}
                    placeholder="MGxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                    optional
                  />

                  <SecretField
                    label="Webhook Verify Token"
                    isSet={status?.webhook_verify_token_set ?? false}
                    maskedValue={null}
                    newValue={webhookToken}
                    editing={editingWebhook}
                    onEdit={() => setEditingWebhook(true)}
                    onCancelEdit={() => { setEditingWebhook(false); setWebhookToken(""); }}
                    onChange={setWebhookToken}
                    onClear={status?.webhook_verify_token_set ? () => handleClearSecret("webhook_verify_token") : undefined}
                    placeholder="En az 8 karakter"
                    hint="Twilio webhook doğrulaması için."
                    optional
                  />
                </div>
              </div>

              {/* Save */}
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={saving}
                  className="px-5 py-2.5 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors disabled:opacity-50 flex items-center gap-2"
                >
                  {saving ? (
                    <>
                      <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      Kaydediliyor…
                    </>
                  ) : (
                    "Ayarları Kaydet"
                  )}
                </button>

                {saveSuccess && (
                  <span className="flex items-center gap-1.5 text-sm text-emerald-400">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    Twilio ayarları güvenli şekilde kaydedildi.
                  </span>
                )}

                {saveError && (
                  <span className="text-sm text-red-400">{saveError}</span>
                )}
              </div>
            </div>
          )}

          {/* ── Tab: Test Mesajı ─────────────────────────────────────── */}
          {activeTab === "test" && (
            <div className="bg-surface border border-border rounded-xl p-5">
              <h2 className="text-sm font-semibold text-text mb-1">Test Mesajı Gönder</h2>
              <p className="text-xs text-text-muted mb-5">
                Yapılandırılmış Twilio provider üzerinden gerçek bir WhatsApp mesajı gönderir.
              </p>

              <div className="space-y-4 mb-5">
                <div>
                  <label className="block text-xs font-medium text-text-muted mb-1.5">
                    Alıcı Telefon Numarası (E.164)
                  </label>
                  <input
                    type="text"
                    value={testPhone}
                    onChange={(e) => setTestPhone(e.target.value)}
                    placeholder="+905001234567"
                    className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text placeholder:text-text-muted/50 focus:outline-none focus:border-accent/50 font-mono"
                  />
                  <p className="mt-1 text-xs text-text-muted/60">
                    Sandbox modunda: telefon numarasının önce Twilio Sandbox&apos;a kayıtlı olması gerekir.
                  </p>
                </div>

                <div>
                  <label className="block text-xs font-medium text-text-muted mb-1.5">
                    Mesaj (opsiyonel)
                  </label>
                  <textarea
                    value={testMessage}
                    onChange={(e) => setTestMessage(e.target.value)}
                    placeholder="Boş bırakılırsa varsayılan test mesajı kullanılır."
                    rows={3}
                    className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text placeholder:text-text-muted/50 focus:outline-none focus:border-accent/50 resize-none"
                  />
                </div>
              </div>

              <button
                type="button"
                onClick={handleTestSend}
                disabled={testSending || !testPhone.trim()}
                className="px-5 py-2.5 bg-surface-2 border border-border rounded-lg text-sm text-text font-medium hover:bg-border transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {testSending ? (
                  <>
                    <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Gönderiliyor…
                  </>
                ) : (
                  <>
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                    </svg>
                    Test Mesajı Gönder
                  </>
                )}
              </button>

              {testResult && (
                <div className="mt-5 p-4 bg-surface-2 border border-border rounded-xl">
                  <p className="text-xs font-semibold text-text-muted mb-3">Sonuç</p>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center gap-3">
                      <span className="text-text-muted w-24 text-xs">Durum</span>
                      <TestResultBadge status={testResult.status} />
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-text-muted w-24 text-xs">Sağlayıcı</span>
                      <code className="text-xs font-mono text-text">{testResult.provider}</code>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-text-muted w-24 text-xs">Alıcı</span>
                      <code className="text-xs font-mono text-text">{testResult.to_phone_masked}</code>
                    </div>
                    {testResult.provider_message_id && (
                      <div className="flex items-center gap-3">
                        <span className="text-text-muted w-24 text-xs">Message SID</span>
                        <code className="text-xs font-mono text-text">{testResult.provider_message_id}</code>
                      </div>
                    )}
                    {testResult.error_message && (
                      <div className="flex items-start gap-3">
                        <span className="text-text-muted w-24 text-xs flex-shrink-0">Hata</span>
                        <span className="text-xs text-red-400">{testResult.error_message}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Tab: Kurulum Rehberi ─────────────────────────────────── */}
          {activeTab === "guide" && (
            <div className="space-y-5">
              <div className="bg-surface border border-border rounded-xl p-5">
                <h2 className="text-sm font-semibold text-text mb-4">Twilio WhatsApp Sandbox Kurulumu</h2>
                <ol className="space-y-4">
                  {[
                    {
                      n: "1",
                      title: "Twilio hesabı açın",
                      desc: "twilio.com adresinden kayıt olun. Console'da Messaging → Try it out → Send a WhatsApp message bölümüne gidin.",
                    },
                    {
                      n: "2",
                      title: "Sandbox'a katılın",
                      desc: "WhatsApp'tan +1 415 523 8886 numarasına \"join <sandbox-kelimesi>\" mesajı gönderin. Kelimeyi Twilio Console'dan bulabilirsiniz.",
                    },
                    {
                      n: "3",
                      title: "Account SID ve Auth Token alın",
                      desc: "Twilio Console → Account Info bölümünden Account SID ve Auth Token değerlerini kopyalayın.",
                    },
                    {
                      n: "4",
                      title: "Ayarlar sekmesinden kaydedin",
                      desc: "Provider olarak \"Twilio Sandbox\" seçin. SID, Auth Token ve From numarasını (whatsapp:+14155238886) girin. Kaydet butonuna tıklayın.",
                    },
                    {
                      n: "5",
                      title: "Webhook URL'ini ayarlayın (opsiyonel)",
                      desc: "Teslimat durumu güncellemeleri için Twilio Console'da webhook URL'ini aşağıdaki adrese ayarlayın.",
                    },
                  ].map((step) => (
                    <li key={step.n} className="flex gap-4">
                      <span className="w-6 h-6 rounded-full bg-accent/10 text-accent text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
                        {step.n}
                      </span>
                      <div>
                        <p className="text-sm font-medium text-text mb-0.5">{step.title}</p>
                        <p className="text-sm text-text-muted">{step.desc}</p>
                      </div>
                    </li>
                  ))}
                </ol>
              </div>

              <div className="bg-surface border border-border rounded-xl p-5">
                <h2 className="text-sm font-semibold text-text mb-4">Ortam Değişkenleri</h2>
                <div className="space-y-3">
                  {[
                    {
                      key: "WHATSAPP_NOTIFICATIONS_ENABLED",
                      val: "true",
                      desc: "WhatsApp bildirimlerini etkinleştir",
                    },
                    {
                      key: "FLOBRIEF_SECRET_ENCRYPTION_KEY",
                      val: "<fernet-key>",
                      desc: "DB'de credential şifrelemek için",
                    },
                    {
                      key: "FRONTEND_PUBLIC_URL",
                      val: "https://yourdomain.com",
                      desc: "Mesajlardaki action linkleri için",
                    },
                  ].map((env) => (
                    <div key={env.key} className="flex items-start gap-3">
                      <code className="text-xs font-mono text-accent bg-accent/5 px-2 py-1 rounded border border-accent/10 flex-shrink-0">
                        {env.key}
                      </code>
                      <div>
                        <code className="text-xs font-mono text-text-muted">{env.val}</code>
                        <p className="text-xs text-text-muted/60 mt-0.5">{env.desc}</p>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-4 pt-4 border-t border-border">
                  <p className="text-xs text-text-muted mb-1">Fernet key üret:</p>
                  <code className="text-xs font-mono text-text-muted bg-surface-2 px-3 py-2 rounded-lg border border-border block">
                    python -c &quot;from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())&quot;
                  </code>
                </div>
              </div>

              <div className="bg-surface border border-border rounded-xl p-5">
                <h2 className="text-sm font-semibold text-text mb-3">Webhook URL</h2>
                <code className="text-xs font-mono text-text-muted bg-surface-2 px-3 py-2 rounded-lg border border-border block">
                  {"POST {BACKEND_URL}/api/v1/webhooks/twilio/whatsapp"}
                </code>
                <p className="mt-2 text-xs text-text-muted">
                  localhost geliştirme ortamı için ngrok veya Cloudflare Tunnel kullanın.
                  URL&apos;yi Twilio Console → Sandbox Settings → Status Callback URL alanına ekleyin.
                </p>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

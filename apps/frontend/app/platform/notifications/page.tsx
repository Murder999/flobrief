"use client";

import {
  resendProviderApi,
  twilioProviderApi,
  type EmailTestSendResult,
  type ResendProviderStatusRead,
  type ResendProviderUpdate,
  type TwilioProviderStatusRead,
  type TwilioProviderUpdate,
  type WhatsAppProviderType,
} from "@/lib/api-client";
import { platformAuthStorage } from "@/lib/platform-auth";
import { useEffect, useState } from "react";

// ── Types ─────────────────────────────────────────────────────────────────────

type Channel = "email" | "whatsapp";

// ── Helpers ───────────────────────────────────────────────────────────────────

function Badge({ ok, label }: { ok: boolean; label: string }) {
  return ok ? (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border bg-emerald-500/10 text-emerald-400 border-emerald-500/20">
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
      {label}
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border bg-[#1e1e2e] text-gray-500 border-[#1e1e2e]">
      <span className="w-1.5 h-1.5 rounded-full bg-gray-600" />
      {label}
    </span>
  );
}

interface SFProps {
  label: string;
  isSet: boolean;
  maskedValue?: string | null;
  newValue: string;
  editing: boolean;
  onEdit: () => void;
  onCancel: () => void;
  onChange: (v: string) => void;
  onClear?: () => void;
  placeholder?: string;
  hint?: string;
  optional?: boolean;
  inputType?: string;
}

function SecretField({
  label, isSet, maskedValue, newValue, editing,
  onEdit, onCancel, onChange, onClear,
  placeholder, hint, optional, inputType = "password",
}: SFProps) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-1.5">
        <label className="text-xs font-medium text-gray-400">{label}</label>
        {optional && (
          <span className="text-[10px] text-gray-600 border border-[#2a2a3e] rounded px-1">opsiyonel</span>
        )}
      </div>
      {editing ? (
        <div className="flex gap-2">
          <input
            type={inputType}
            value={newValue}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder ?? "Yeni değer girin"}
            autoComplete="new-password"
            className="flex-1 bg-[#0c0c12] border border-indigo-500/40 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder:text-gray-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/20 font-mono"
          />
          <button type="button" onClick={onCancel}
            className="px-3 py-2 text-xs text-gray-400 border border-[#2a2a3e] rounded-lg hover:bg-[#1e1e2e] transition-colors">
            İptal
          </button>
        </div>
      ) : isSet ? (
        <div className="flex items-center gap-2">
          <div className="flex-1 bg-[#0c0c12] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-gray-500 font-mono">
            {maskedValue ?? "••••••••••••"}
          </div>
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex-shrink-0">
            ✓ Kayıtlı
          </span>
          <button type="button" onClick={onEdit}
            className="text-xs text-indigo-400 hover:text-indigo-300 px-2 py-1 flex-shrink-0">
            Değiştir
          </button>
          {onClear && (
            <button type="button" onClick={onClear}
              className="text-xs text-red-400/60 hover:text-red-400 px-2 py-1 flex-shrink-0">
              Sil
            </button>
          )}
        </div>
      ) : (
        <button type="button" onClick={onEdit}
          className="w-full bg-[#0c0c12] border border-dashed border-[#2a2a3e] rounded-lg px-3 py-2.5 text-sm text-gray-500 text-left hover:border-indigo-500/30 hover:text-gray-300 transition-colors flex items-center gap-2">
          <svg className="w-3.5 h-3.5 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          {optional ? "Eklemek için tıklayın (opsiyonel)" : "Ayarlamak için tıklayın"}
        </button>
      )}
      {hint && <p className="mt-1.5 text-xs text-gray-600">{hint}</p>}
    </div>
  );
}

function TextField({ label, value, onChange, placeholder, hint, optional }: {
  label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; hint?: string; optional?: boolean;
}) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-1.5">
        <label className="text-xs font-medium text-gray-400">{label}</label>
        {optional && <span className="text-[10px] text-gray-600 border border-[#2a2a3e] rounded px-1">opsiyonel</span>}
      </div>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-[#0c0c12] border border-[#2a2a3e] rounded-lg px-3 py-2 text-sm text-gray-200 placeholder:text-gray-600 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20"
      />
      {hint && <p className="mt-1.5 text-xs text-gray-600">{hint}</p>}
    </div>
  );
}

// ── Email Section ─────────────────────────────────────────────────────────────

function EmailProviderSection() {
  const [status, setStatus] = useState<ResendProviderStatusRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [activeTab, setActiveTab] = useState<"settings" | "test">("settings");

  const [isEnabled, setIsEnabled] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [editingKey, setEditingKey] = useState(false);
  const [fromName, setFromName] = useState("");
  const [fromEmail, setFromEmail] = useState("");
  const [replyTo, setReplyTo] = useState("");

  const [testEmail, setTestEmail] = useState("");
  const [testSubject, setTestSubject] = useState("");
  const [testMessage, setTestMessage] = useState("");
  const [testSending, setTestSending] = useState(false);
  const [testResult, setTestResult] = useState<EmailTestSendResult | null>(null);

  const applyStatus = (data: ResendProviderStatusRead) => {
    setStatus(data);
    setIsEnabled(data.is_enabled);
    setFromName(data.from_name ?? "");
    setFromEmail(data.from_email ?? "");
    setReplyTo(data.reply_to ?? "");
  };

  const load = async () => {
    const token = platformAuthStorage.getToken();
    if (!token) { setLoading(false); return; }
    setLoading(true); setLoadError(null);
    try {
      applyStatus(await resendProviderApi.getStatus(token));
    } catch (e: unknown) {
      const err = e as { message?: string };
      setLoadError(err?.message ?? "Resend ayarları yüklenemedi.");
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSave = async () => {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setSaving(true); setSaveError(null); setSaveSuccess(false);
    const update: ResendProviderUpdate = {
      is_enabled: isEnabled,
      from_name: fromName || undefined,
      from_email: fromEmail || undefined,
      reply_to: replyTo || null,
    };
    if (editingKey && apiKey.trim()) update.api_key = apiKey.trim();
    try {
      applyStatus(await resendProviderApi.update(update, token));
      setEditingKey(false); setApiKey("");
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 4000);
    } catch (e: unknown) {
      const err = e as { message?: string };
      setSaveError(err?.message ?? "Kaydedilemedi.");
    } finally { setSaving(false); }
  };

  const handleClearApiKey = async () => {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    if (!confirm("API Key kalıcı olarak silinecek. Emin misiniz?")) return;
    try {
      applyStatus(await resendProviderApi.clearApiKey(token));
    } catch (e: unknown) {
      const err = e as { message?: string };
      alert(err?.message ?? "API Key silinemedi.");
    }
  };

  const handleTestSend = async () => {
    const token = platformAuthStorage.getToken();
    if (!token || !testEmail.trim()) return;
    setTestSending(true); setTestResult(null);
    try {
      const result = await resendProviderApi.testSend({
        to_email: testEmail.trim(),
        subject: testSubject.trim() || undefined,
        message: testMessage.trim() || undefined,
      }, token);
      setTestResult(result);
    } catch (e: unknown) {
      const err = e as { message?: string };
      setTestResult({
        status: "failed", provider: "unknown",
        provider_message_id: null,
        error_message: err?.message ?? "Test gönderilemedi.",
        to_email_masked: "***",
      });
    } finally { setTestSending(false); }
  };

  return (
    <div className="space-y-5">
      {/* Status bar */}
      {!loading && status && (
        <div className="bg-[#111118] border border-[#1e1e2e] rounded-xl px-5 py-3.5 flex items-center gap-4 flex-wrap">
          <Badge ok={status.is_configured && status.is_enabled} label={
            !status.is_configured ? "Yapılandırılmamış" :
            !status.is_enabled ? "Devre Dışı" : "Aktif"
          } />
          <span className="text-xs rounded-full border border-[#2a2a3e] px-2.5 py-1 text-gray-400">
            Kaynak: {status.configuration_source === "database" ? "Veritabanı" : status.configuration_source === "environment" ? "Sunucu ortamı" : "Yok"}
          </span>
          <div className="flex items-center gap-6 text-xs text-gray-500 flex-wrap">
            {status.from_email && <span>From: <code className="font-mono text-gray-300">{status.from_email}</code></span>}
            {status.email_api_key_masked && <span>API Key: <code className="font-mono text-gray-300">{status.email_api_key_masked}</code></span>}
            {status.configured_at && <span>Güncellendi: {new Date(status.configured_at).toLocaleString("tr-TR")}</span>}
          </div>
          {(status.missing_fields?.length ?? 0) > 0 && (
            <span className="ml-auto text-xs text-amber-400">Eksik: {status.missing_fields.join(", ")}</span>
          )}
        </div>
      )}

      {loadError && !loading && (
        <div className="px-4 py-3 bg-red-500/5 border border-red-500/20 rounded-xl text-sm text-red-400 flex items-center gap-3">
          <span>{loadError}</span>
          <button onClick={load} className="ml-auto text-xs text-indigo-400 hover:underline">Tekrar dene</button>
        </div>
      )}
      {loading && (
        <div className="bg-[#111118] border border-[#1e1e2e] rounded-xl p-6 animate-pulse space-y-3">
          {[1, 2, 3].map((i) => <div key={i} className="h-10 bg-[#1e1e2e] rounded-lg" />)}
        </div>
      )}

      {!loading && (
        <>
          <div className="flex gap-1 bg-[#0c0c12] p-1 rounded-xl">
            {(["settings", "test"] as const).map((tab) => (
              <button key={tab} onClick={() => setActiveTab(tab)}
                className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all ${
                  activeTab === tab
                    ? "bg-[#111118] text-gray-100 shadow-sm border border-[#2a2a3e]"
                    : "text-gray-500 hover:text-gray-300"
                }`}>
                {tab === "settings" ? "Ayarlar" : "Test E-postası"}
              </button>
            ))}
          </div>

          {activeTab === "settings" && (
            <div className="space-y-5">
              {/* Enable toggle */}
              <div className="bg-[#111118] border border-[#1e1e2e] rounded-xl p-5">
                <h2 className="text-sm font-semibold text-gray-100 mb-4">E-posta Provider Durumu</h2>
                <div
                  className="flex items-center gap-3 p-3 bg-[#0c0c12] rounded-lg cursor-pointer"
                  onClick={() => status?.configuration_source !== "environment" && setIsEnabled(!isEnabled)}
                >
                  <button type="button" disabled={status?.configuration_source === "environment"}
                    className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors flex-shrink-0 ${isEnabled ? "bg-indigo-500" : "bg-[#2a2a3e]"}`}>
                    <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${isEnabled ? "translate-x-4" : "translate-x-0.5"}`} />
                  </button>
                  <div>
                    <p className="text-sm font-medium text-gray-200">E-posta Bildirimleri</p>
                    <p className="text-xs text-gray-500">
                      {status?.configuration_source === "environment"
                        ? "Sunucu ortam değişkenleriyle aktif; kapatmak için RESEND_API_KEY kaldırılmalıdır"
                        : isEnabled ? "Aktif — e-postalar Resend üzerinden gönderilecek" : "Devre dışı — e-postalar gönderilmeyecek"}
                    </p>
                  </div>
                </div>
              </div>

              {/* Credentials */}
              <div className="bg-[#111118] border border-[#1e1e2e] rounded-xl p-5">
                <h2 className="text-sm font-semibold text-gray-100 mb-4">Resend API Bilgileri</h2>
                <div className="space-y-4">
                  <SecretField
                    label="Resend API Key"
                    isSet={status?.api_key_set ?? false}
                    maskedValue={status?.email_api_key_masked}
                    newValue={apiKey}
                    editing={editingKey}
                    onEdit={() => setEditingKey(true)}
                    onCancel={() => { setEditingKey(false); setApiKey(""); }}
                    onChange={setApiKey}
                    onClear={status?.configuration_source === "database" ? handleClearApiKey : undefined}
                    placeholder="re_xxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                    hint="Resend Dashboard → API Keys → Create API Key"
                  />
                </div>
              </div>

              {/* From / Reply-To */}
              <div className="bg-[#111118] border border-[#1e1e2e] rounded-xl p-5">
                <h2 className="text-sm font-semibold text-gray-100 mb-4">Gönderici Bilgileri</h2>
                <div className="space-y-4">
                  <TextField
                    label="From Name"
                    value={fromName}
                    onChange={setFromName}
                    placeholder="PostPiloter"
                    hint="E-posta gönderici adı"
                  />
                  <TextField
                    label="From Email"
                    value={fromEmail}
                    onChange={setFromEmail}
                    placeholder="noreply@postpiloter.com"
                    hint="Resend tarafında doğrulanmış domain'den bir adres kullanın"
                  />
                  <TextField
                    label="Reply-To Email"
                    value={replyTo}
                    onChange={setReplyTo}
                    placeholder=""
                    hint="Opsiyonel. Kullanıcıların yanıtları bu adrese gider."
                    optional
                  />
                </div>
              </div>

              {/* Save */}
              <div className="flex items-center gap-3">
                <button type="button" onClick={handleSave} disabled={saving}
                  className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50 flex items-center gap-2">
                  {saving ? (
                    <><svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>Kaydediliyor…</>
                  ) : "Ayarları Kaydet"}
                </button>
                {saveSuccess && (
                  <span className="flex items-center gap-1.5 text-sm text-emerald-400">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    Resend ayarları şifreli olarak kaydedildi.
                  </span>
                )}
                {saveError && <span className="text-sm text-red-400">{saveError}</span>}
              </div>

              {/* Guide */}
              <div className="bg-[#111118] border border-[#1e1e2e] rounded-xl p-5">
                <h2 className="text-sm font-semibold text-gray-100 mb-3">Kurulum Notu</h2>
                <ul className="space-y-2 text-xs text-gray-500">
                  <li>• <strong className="text-gray-400">resend.com</strong> adresinden API Key oluşturun.</li>
                  <li>• Resend Dashboard → Domains kısmından gönderici domain&apos;inizi doğrulayın.</li>
                  <li>• From Email mutlaka doğrulanmış bir domain&apos;e ait olmalıdır.</li>
                  <li>• API Key sadece şifreli olarak saklanır; hiçbir zaman geri döndürülmez.</li>
                </ul>
                <div className="mt-4 p-3 bg-[#0c0c12] rounded-lg border border-[#1e1e2e]">
                  <p className="text-xs text-gray-500 mb-1">Production ortamında sunucu secret&apos;ı yetkilidir. Diğer ortamlarda geçerli ve aktif DB ayarı önceliklidir; DB kaydı kullanılamazsa ortam ayarı fallback olur:</p>
                  <code className="text-xs font-mono text-indigo-300">RESEND_API_KEY=re_xxxx</code>
                </div>
              </div>
            </div>
          )}

          {activeTab === "test" && (
            <div className="bg-[#111118] border border-[#1e1e2e] rounded-xl p-5">
              <h2 className="text-sm font-semibold text-gray-100 mb-1">Test E-postası Gönder</h2>
              <p className="text-xs text-gray-500 mb-5">
                Yapılandırılmış Resend provider üzerinden gerçek bir e-posta gönderir.
              </p>
              {!status?.is_configured && (
                <div className="mb-4 px-4 py-3 bg-amber-500/5 border border-amber-500/20 rounded-lg text-xs text-amber-400">
                  Provider henüz yapılandırılmamış. API Key ve From Email ayarlarını kaydedin.
                </div>
              )}
              <div className="space-y-4 mb-5">
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1.5">Alıcı E-posta Adresi</label>
                  <input type="email" value={testEmail} onChange={(e) => setTestEmail(e.target.value)}
                    placeholder="test@example.com"
                    className="w-full bg-[#0c0c12] border border-[#2a2a3e] rounded-lg px-3 py-2 text-sm text-gray-200 placeholder:text-gray-600 focus:outline-none focus:border-indigo-500/50" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1.5">Konu (opsiyonel)</label>
                  <input type="text" value={testSubject} onChange={(e) => setTestSubject(e.target.value)}
                    placeholder="PostPiloter — Test E-postası"
                    className="w-full bg-[#0c0c12] border border-[#2a2a3e] rounded-lg px-3 py-2 text-sm text-gray-200 placeholder:text-gray-600 focus:outline-none focus:border-indigo-500/50" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1.5">Mesaj (opsiyonel)</label>
                  <textarea value={testMessage} onChange={(e) => setTestMessage(e.target.value)}
                    placeholder="Boş bırakılırsa varsayılan mesaj kullanılır."
                    rows={3}
                    className="w-full bg-[#0c0c12] border border-[#2a2a3e] rounded-lg px-3 py-2 text-sm text-gray-200 placeholder:text-gray-600 focus:outline-none focus:border-indigo-500/50 resize-none" />
                </div>
              </div>
              <button type="button" onClick={handleTestSend}
                disabled={testSending || !testEmail.trim() || !status?.is_configured}
                className="px-5 py-2.5 bg-[#1e1e2e] border border-[#2a2a3e] rounded-lg text-sm text-gray-200 font-medium hover:bg-[#2a2a3e] transition-colors disabled:opacity-50 flex items-center gap-2">
                {testSending ? (
                  <><svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>Gönderiliyor…</>
                ) : (
                  <><svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>Test Maili Gönder</>
                )}
              </button>
              {testResult && (
                <div className="mt-5 p-4 bg-[#0c0c12] border border-[#1e1e2e] rounded-xl">
                  <p className="text-xs font-semibold text-gray-500 mb-3 uppercase tracking-wider">Sonuç</p>
                  <div className="space-y-2">
                    <div className="flex items-center gap-3">
                      <span className="text-gray-500 w-28 text-xs">Durum</span>
                      <code className={`text-xs font-mono px-2 py-0.5 rounded border ${
                        testResult.status === "sent"
                          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                          : "bg-red-500/10 text-red-400 border-red-500/20"
                      }`}>{testResult.status}</code>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-gray-500 w-28 text-xs">Sağlayıcı</span>
                      <code className="text-xs font-mono text-gray-300">{testResult.provider}</code>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-gray-500 w-28 text-xs">Alıcı</span>
                      <code className="text-xs font-mono text-gray-300">{testResult.to_email_masked}</code>
                    </div>
                    {testResult.provider_message_id && (
                      <div className="flex items-center gap-3">
                        <span className="text-gray-500 w-28 text-xs">Message ID</span>
                        <code className="text-xs font-mono text-gray-300">{testResult.provider_message_id}</code>
                      </div>
                    )}
                    {testResult.error_message && (
                      <div className="flex items-start gap-3">
                        <span className="text-gray-500 w-28 text-xs flex-shrink-0">Hata</span>
                        <span className="text-xs text-red-400">{testResult.error_message}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── WhatsApp Section (existing) ───────────────────────────────────────────────

const PROVIDER_TYPES: { value: WhatsAppProviderType; label: string; desc: string }[] = [
  { value: "disabled", label: "Devre Dışı", desc: "WhatsApp gönderimi kapalı" },
  { value: "twilio_sandbox", label: "Twilio Sandbox", desc: "Geliştirme ve test için" },
  { value: "twilio_production", label: "Twilio Production", desc: "Canlı Business hesabı" },
];

function WhatsAppProviderSection() {
  const [activeTab, setActiveTab] = useState<"settings" | "test" | "guide">("settings");
  const [status, setStatus] = useState<TwilioProviderStatusRead | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

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
  const [testPhone, setTestPhone] = useState("");
  const [testMessage, setTestMessage] = useState("");
  const [testSending, setTestSending] = useState(false);
  const [testResult, setTestResult] = useState<{
    status: string; provider: string;
    provider_message_id: string | null; error_message: string | null; to_phone_masked: string;
  } | null>(null);

  const applyStatus = (data: TwilioProviderStatusRead) => {
    setStatus(data);
    setProviderType(data.provider_type as WhatsAppProviderType);
    setIsEnabled(data.is_enabled);
  };

  const loadStatus = async () => {
    const token = platformAuthStorage.getToken();
    if (!token) { setLoading(false); return; }
    setLoading(true); setLoadError(null);
    try { applyStatus(await twilioProviderApi.getStatus(token)); }
    catch (e: unknown) {
      const err = e as { message?: string };
      setLoadError(err?.message ?? "Twilio ayarları yüklenemedi.");
    } finally { setLoading(false); }
  };

  useEffect(() => { loadStatus(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSave = async () => {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setSaving(true); setSaveError(null); setSaveSuccess(false);
    const update: TwilioProviderUpdate = { provider_type: providerType, is_enabled: isEnabled };
    if (editingSid && accountSid.trim()) update.account_sid = accountSid.trim();
    if (editingToken && authToken.trim()) update.auth_token = authToken.trim();
    if (editingFrom && whatsappFrom.trim()) update.whatsapp_from = whatsappFrom.trim();
    if (editingMsid && messagingSid.trim()) update.messaging_service_sid = messagingSid.trim();
    if (editingWebhook && webhookToken.trim()) update.webhook_verify_token = webhookToken.trim();
    try {
      const updated = await twilioProviderApi.update(update, token);
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
    } finally { setSaving(false); }
  };

  const handleClearSecret = async (field: "auth_token" | "account_sid" | "whatsapp_from" | "messaging_service_sid" | "webhook_verify_token") => {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    if (!confirm("Bu secret kalıcı olarak silinecek. Emin misiniz?")) return;
    try { applyStatus(await twilioProviderApi.clearSecret(field, token)); }
    catch (e: unknown) { const err = e as { message?: string }; alert(err?.message ?? "Secret silinemedi."); }
  };

  const handleTestSend = async () => {
    const token = platformAuthStorage.getToken();
    if (!token || !testPhone.trim()) return;
    setTestSending(true); setTestResult(null);
    try {
      const result = await twilioProviderApi.testSend({ to_phone: testPhone.trim(), message: testMessage.trim() || undefined }, token);
      setTestResult(result);
    } catch (e: unknown) {
      const err = e as { message?: string };
      setTestResult({ status: "failed", provider: "unknown", provider_message_id: null, error_message: err?.message ?? "Test gönderilemedi.", to_phone_masked: "***" });
    } finally { setTestSending(false); }
  };

  return (
    <div className="space-y-5">
      {!loading && status && (
        <div className="bg-[#111118] border border-[#1e1e2e] rounded-xl px-5 py-3.5 flex items-center gap-4 flex-wrap">
          <Badge ok={status.is_configured && status.is_enabled} label={
            !status.is_configured ? "Yapılandırılmamış" : !status.is_enabled ? "Devre Dışı" : "Aktif"
          } />
          <div className="flex items-center gap-6 text-xs text-gray-500 flex-wrap">
            {status.account_sid_masked && <span>SID: <code className="font-mono text-gray-300">{status.account_sid_masked}</code></span>}
            {status.whatsapp_from_masked && <span>From: <code className="font-mono text-gray-300">{status.whatsapp_from_masked}</code></span>}
            {status.configured_at && <span>Güncellendi: {new Date(status.configured_at).toLocaleString("tr-TR")}</span>}
          </div>
          {(status.missing_fields?.length ?? 0) > 0 && (
            <span className="ml-auto text-xs text-amber-400">Eksik: {status.missing_fields.join(", ")}</span>
          )}
        </div>
      )}
      {loadError && !loading && (
        <div className="px-4 py-3 bg-red-500/5 border border-red-500/20 rounded-xl text-sm text-red-400 flex items-center gap-3">
          <span>{loadError}</span>
          <button onClick={loadStatus} className="ml-auto text-xs text-indigo-400 hover:underline">Tekrar dene</button>
        </div>
      )}
      {loading && (
        <div className="bg-[#111118] border border-[#1e1e2e] rounded-xl p-6 animate-pulse space-y-3">
          {[1, 2, 3].map((i) => <div key={i} className="h-10 bg-[#1e1e2e] rounded-lg" />)}
        </div>
      )}
      {!loading && (
        <>
          <div className="flex gap-1 bg-[#0c0c12] p-1 rounded-xl">
            {(["settings", "test", "guide"] as const).map((tab) => (
              <button key={tab} onClick={() => setActiveTab(tab)}
                className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all ${
                  activeTab === tab ? "bg-[#111118] text-gray-100 shadow-sm border border-[#2a2a3e]" : "text-gray-500 hover:text-gray-300"
                }`}>
                {tab === "settings" ? "Ayarlar" : tab === "test" ? "Test Mesajı" : "Rehber"}
              </button>
            ))}
          </div>

          {activeTab === "settings" && (
            <div className="space-y-5">
              <div className="bg-[#111118] border border-[#1e1e2e] rounded-xl p-5">
                <h2 className="text-sm font-semibold text-gray-100 mb-4">Sağlayıcı Yapılandırması</h2>
                <div className="mb-4">
                  <label className="block text-xs font-medium text-gray-400 mb-1.5">WhatsApp Sağlayıcısı</label>
                  <select value={providerType} onChange={(e) => setProviderType(e.target.value as WhatsAppProviderType)}
                    className="w-full bg-[#0c0c12] border border-[#2a2a3e] rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500/50">
                    {PROVIDER_TYPES.map((o) => <option key={o.value} value={o.value}>{o.label} — {o.desc}</option>)}
                  </select>
                </div>
                <div className="flex items-center gap-3 p-3 bg-[#0c0c12] rounded-lg cursor-pointer" onClick={() => setIsEnabled(!isEnabled)}>
                  <button type="button" className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors flex-shrink-0 ${isEnabled ? "bg-indigo-500" : "bg-[#2a2a3e]"}`}>
                    <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${isEnabled ? "translate-x-4" : "translate-x-0.5"}`} />
                  </button>
                  <div>
                    <p className="text-sm font-medium text-gray-200">WhatsApp Bildirimleri</p>
                    <p className="text-xs text-gray-500">{isEnabled ? "Aktif" : "Devre dışı"}</p>
                  </div>
                </div>
              </div>
              <div className="bg-[#111118] border border-[#1e1e2e] rounded-xl p-5">
                <h2 className="text-sm font-semibold text-gray-100 mb-4">Twilio API Bilgileri</h2>
                <div className="space-y-4">
                  <SecretField label="Account SID" isSet={!!status?.account_sid_masked} maskedValue={status?.account_sid_masked} newValue={accountSid} editing={editingSid} onEdit={() => setEditingSid(true)} onCancel={() => { setEditingSid(false); setAccountSid(""); }} onChange={setAccountSid} onClear={status?.account_sid_masked ? () => handleClearSecret("account_sid") : undefined} placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" hint="Twilio Console → Account Info → Account SID" />
                  <SecretField label="Auth Token" isSet={status?.auth_token_set ?? false} maskedValue={null} newValue={authToken} editing={editingToken} onEdit={() => setEditingToken(true)} onCancel={() => { setEditingToken(false); setAuthToken(""); }} onChange={setAuthToken} onClear={status?.auth_token_set ? () => handleClearSecret("auth_token") : undefined} placeholder="Auth token girin" hint="Hiçbir zaman geri döndürülmez." />
                  <SecretField label="WhatsApp From Numarası" isSet={!!status?.whatsapp_from_masked} maskedValue={status?.whatsapp_from_masked} newValue={whatsappFrom} editing={editingFrom} onEdit={() => setEditingFrom(true)} onCancel={() => { setEditingFrom(false); setWhatsappFrom(""); }} onChange={setWhatsappFrom} onClear={status?.whatsapp_from_masked ? () => handleClearSecret("whatsapp_from") : undefined} placeholder="whatsapp:+14155238886" />
                  <SecretField label="Messaging Service SID" isSet={status?.messaging_service_sid_set ?? false} maskedValue={null} newValue={messagingSid} editing={editingMsid} onEdit={() => setEditingMsid(true)} onCancel={() => { setEditingMsid(false); setMessagingSid(""); }} onChange={setMessagingSid} onClear={status?.messaging_service_sid_set ? () => handleClearSecret("messaging_service_sid") : undefined} placeholder="MGxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" optional />
                  <SecretField label="Webhook Verify Token" isSet={status?.webhook_verify_token_set ?? false} maskedValue={null} newValue={webhookToken} editing={editingWebhook} onEdit={() => setEditingWebhook(true)} onCancel={() => { setEditingWebhook(false); setWebhookToken(""); }} onChange={setWebhookToken} onClear={status?.webhook_verify_token_set ? () => handleClearSecret("webhook_verify_token") : undefined} placeholder="En az 8 karakter" optional />
                </div>
              </div>
              <div className="flex items-center gap-3">
                <button type="button" onClick={handleSave} disabled={saving}
                  className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50">
                  {saving ? "Kaydediliyor…" : "Ayarları Kaydet"}
                </button>
                {saveSuccess && <span className="text-sm text-emerald-400">✓ Twilio ayarları kaydedildi.</span>}
                {saveError && <span className="text-sm text-red-400">{saveError}</span>}
              </div>
            </div>
          )}

          {activeTab === "test" && (
            <div className="bg-[#111118] border border-[#1e1e2e] rounded-xl p-5">
              <h2 className="text-sm font-semibold text-gray-100 mb-4">Test Mesajı Gönder</h2>
              <div className="space-y-4 mb-5">
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1.5">Alıcı Telefon (E.164)</label>
                  <input type="text" value={testPhone} onChange={(e) => setTestPhone(e.target.value)} placeholder="+905001234567"
                    className="w-full bg-[#0c0c12] border border-[#2a2a3e] rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500/50 font-mono" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1.5">Mesaj (opsiyonel)</label>
                  <textarea value={testMessage} onChange={(e) => setTestMessage(e.target.value)} rows={3}
                    placeholder="Boş bırakılırsa varsayılan mesaj kullanılır."
                    className="w-full bg-[#0c0c12] border border-[#2a2a3e] rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500/50 resize-none" />
                </div>
              </div>
              <button type="button" onClick={handleTestSend} disabled={testSending || !testPhone.trim()}
                className="px-5 py-2.5 bg-[#1e1e2e] border border-[#2a2a3e] rounded-lg text-sm text-gray-200 font-medium hover:bg-[#2a2a3e] transition-colors disabled:opacity-50">
                {testSending ? "Gönderiliyor…" : "Test Mesajı Gönder"}
              </button>
              {testResult && (
                <div className="mt-5 p-4 bg-[#0c0c12] border border-[#1e1e2e] rounded-xl">
                  <p className="text-xs font-semibold text-gray-500 mb-3 uppercase tracking-wider">Sonuç</p>
                  <div className="space-y-2">
                    <div className="flex items-center gap-3">
                      <span className="text-gray-500 w-28 text-xs">Durum</span>
                      <code className={`text-xs font-mono px-2 py-0.5 rounded border ${testResult.status === "sent" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-red-500/10 text-red-400 border-red-500/20"}`}>{testResult.status}</code>
                    </div>
                    {testResult.provider_message_id && (
                      <div className="flex items-center gap-3"><span className="text-gray-500 w-28 text-xs">Message SID</span><code className="text-xs font-mono text-gray-300">{testResult.provider_message_id}</code></div>
                    )}
                    {testResult.error_message && (
                      <div className="flex items-start gap-3"><span className="text-gray-500 w-28 text-xs flex-shrink-0">Hata</span><span className="text-xs text-red-400">{testResult.error_message}</span></div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === "guide" && (
            <div className="bg-[#111118] border border-[#1e1e2e] rounded-xl p-5">
              <h2 className="text-sm font-semibold text-gray-100 mb-4">Twilio WhatsApp Sandbox Kurulumu</h2>
              <ol className="space-y-4">
                {[
                  { n: "1", title: "Twilio hesabı açın", desc: "twilio.com adresinden kayıt olun. Console → Messaging → Try it out → Send a WhatsApp message bölümüne gidin." },
                  { n: "2", title: "Sandbox'a katılın", desc: "WhatsApp'tan +1 415 523 8886 numarasına \"join <sandbox-kelimesi>\" mesajı gönderin." },
                  { n: "3", title: "Account SID ve Auth Token alın", desc: "Twilio Console → Account Info değerlerini kopyalayın." },
                  { n: "4", title: "Ayarları kaydedin", desc: "Provider olarak \"Twilio Sandbox\" seçin, bilgileri girin ve kaydedin." },
                ].map((step) => (
                  <li key={step.n} className="flex gap-4">
                    <span className="w-6 h-6 rounded-full bg-indigo-500/10 text-indigo-400 text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">{step.n}</span>
                    <div>
                      <p className="text-sm font-medium text-gray-200 mb-0.5">{step.title}</p>
                      <p className="text-sm text-gray-400">{step.desc}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function PlatformNotificationsPage() {
  const [channel, setChannel] = useState<Channel>("email");

  const channels: { id: Channel; label: string; icon: string }[] = [
    { id: "email", label: "E-posta / Resend", icon: "✉" },
    { id: "whatsapp", label: "WhatsApp / Twilio", icon: "💬" },
  ];

  return (
    <div className="p-8 max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <p className="text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-1">Platform Ayarları</p>
        <h1 className="text-2xl font-bold text-gray-100">Bildirim Kanalları</h1>
        <p className="mt-1 text-gray-400">E-posta ve WhatsApp bildirim provider yapılandırması.</p>
      </div>

      {/* Channel selector */}
      <div className="grid grid-cols-2 gap-3 mb-8">
        {channels.map((ch) => (
          <button key={ch.id} onClick={() => setChannel(ch.id)}
            className={`flex items-center gap-3 p-4 rounded-xl border transition-all text-left ${
              channel === ch.id
                ? "bg-[#111118] border-indigo-500/30 shadow-md shadow-indigo-500/5"
                : "bg-[#0c0c12] border-[#1e1e2e] hover:border-[#2a2a3e]"
            }`}>
            <span className="text-2xl">{ch.icon}</span>
            <div>
              <p className={`text-sm font-semibold ${channel === ch.id ? "text-gray-100" : "text-gray-400"}`}>{ch.label}</p>
              <p className="text-xs text-gray-600 mt-0.5">
                {ch.id === "email" ? "Resend API ile gerçek e-posta" : "Twilio WhatsApp mesajlaşma"}
              </p>
            </div>
          </button>
        ))}
      </div>

      {channel === "email" && <EmailProviderSection />}
      {channel === "whatsapp" && <WhatsAppProviderSection />}
    </div>
  );
}

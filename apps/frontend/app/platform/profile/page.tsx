"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ApiError,
  authApi,
  sessionsApi,
  type AuthUser,
  type SessionRead,
} from "@/lib/api-client";
import { PasswordChangeForm } from "@/components/settings/password-change-form";
import { MfaSetupCard } from "@/components/settings/mfa-setup-card";
import { platformAuthStorage } from "@/lib/platform-auth";

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("tr-TR", { day: "2-digit", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function parseDevice(userAgent: string | null): string {
  if (!userAgent) return "Bilinmeyen cihaz";
  if (/iphone|ipad/i.test(userAgent)) return "iOS cihaz";
  if (/android/i.test(userAgent)) return "Android cihaz";
  if (/windows/i.test(userAgent)) return "Windows";
  if (/mac os/i.test(userAgent)) return "macOS";
  if (/linux/i.test(userAgent)) return "Linux";
  return "Bilinmeyen cihaz";
}

type Tab = "personal" | "security" | "sessions";

export default function PlatformProfilePage() {
  const router = useRouter();
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("personal");

  const [fullName, setFullName] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const [sessions, setSessions] = useState<SessionRead[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [revokingId, setRevokingId] = useState<string | null>(null);

  function loadUser(token: string) {
    authApi.me(token).then((u) => {
      setUser(u);
      setFullName(u.full_name);
      setJobTitle(u.job_title ?? "");
    }).catch(() => {}).finally(() => setLoading(false));
  }

  useEffect(() => {
    const token = platformAuthStorage.getToken();
    setAccessToken(token);
    if (!token) { router.replace("/platform/login"); return; }
    loadUser(token);
  }, [router]);

  function loadSessions() {
    if (!accessToken) return;
    setSessionsLoading(true);
    sessionsApi.list(accessToken).then(setSessions).catch(() => {}).finally(() => setSessionsLoading(false));
  }

  useEffect(() => {
    if (tab === "sessions" && accessToken) loadSessions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, accessToken]);

  async function handleSaveProfile() {
    if (!accessToken || !fullName.trim()) return;
    setSaving(true);
    setSaveMsg(null);
    try {
      const updated = await authApi.updateProfile({ full_name: fullName.trim(), job_title: jobTitle.trim() || null }, accessToken);
      setUser(updated);
      setSaveMsg({ type: "ok", text: "Profil güncellendi." });
    } catch (e) {
      setSaveMsg({ type: "err", text: e instanceof ApiError ? e.message : "Kaydedilemedi." });
    } finally {
      setSaving(false);
    }
  }

  async function handleRevokeSession(id: string) {
    if (!accessToken) return;
    setRevokingId(id);
    try {
      await sessionsApi.revoke(id, accessToken);
      setSessions((prev) => prev.filter((s) => s.id !== id));
    } catch { /* keep list as-is on failure */ } finally {
      setRevokingId(null);
    }
  }

  async function handleRevokeAll() {
    if (!accessToken) return;
    if (!window.confirm("Tüm oturumlar kapatılacak ve yeniden giriş yapmanız gerekecek. Devam edilsin mi?")) return;
    try {
      await sessionsApi.revokeAll(accessToken);
    } finally {
      platformAuthStorage.clearAll();
      router.replace("/platform/login");
    }
  }

  function handlePasswordChangeCompleted() {
    platformAuthStorage.clearAll();
    router.replace("/platform/login");
  }

  const isDirty = user ? (fullName !== user.full_name || jobTitle !== (user.job_title ?? "")) : false;

  const tabs: { id: Tab; label: string }[] = [
    { id: "personal", label: "Kişisel Bilgiler" },
    { id: "security", label: "Güvenlik" },
    { id: "sessions", label: "Aktif Oturumlar" },
  ];

  return (
    <div className="mx-auto w-full max-w-2xl px-6 py-10">
      <div className="mb-8">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent">Platform Yöneticisi</p>
        <h1 className="mt-2 text-2xl font-bold tracking-tight text-text">Profil ve Güvenlik</h1>
        <p className="mt-1 text-sm text-text-muted">Hesap bilgilerinizi, güvenlik ayarlarınızı ve aktif oturumlarınızı yönetin.</p>
      </div>

      <div className="flex items-center gap-1 mb-6 bg-surface-2 border border-border rounded-xl p-1 w-fit">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${tab === t.id ? "bg-surface text-text shadow-sm" : "text-text-muted hover:text-text"}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-32 bg-surface-2 rounded-2xl animate-pulse" />)}
        </div>
      ) : (
        <>
          {tab === "personal" && (
            <div className="bg-surface border border-border rounded-2xl p-6 space-y-5">
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 bg-accent/20 rounded-full flex items-center justify-center flex-shrink-0">
                  <span className="text-lg font-bold text-accent">
                    {user?.full_name?.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase() ?? "?"}
                  </span>
                </div>
                <div>
                  <p className="text-base font-semibold text-text">{user?.full_name ?? "—"}</p>
                  <p className="text-sm text-text-muted">{user?.email ?? "—"}</p>
                </div>
              </div>

              <div className="space-y-4">
                <div>
                  <label htmlFor="profile-full-name" className="block text-sm font-medium text-text mb-1.5">Ad Soyad</label>
                  <input
                    id="profile-full-name"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="w-full px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
                  />
                </div>
                <div>
                  <label htmlFor="profile-job-title" className="block text-sm font-medium text-text mb-1.5">Unvan</label>
                  <input
                    id="profile-job-title"
                    value={jobTitle}
                    onChange={(e) => setJobTitle(e.target.value)}
                    placeholder="örn. Platform Operasyon Yöneticisi"
                    className="w-full px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
                  />
                </div>

                {saveMsg && (
                  <div className={`p-3 rounded-lg text-sm ${saveMsg.type === "ok" ? "bg-success/10 border border-success/20 text-success" : "bg-danger/10 border border-danger/20 text-danger"}`}>
                    {saveMsg.text}
                  </div>
                )}

                <button
                  onClick={handleSaveProfile}
                  disabled={saving || !isDirty || !fullName.trim()}
                  className="px-5 py-2.5 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 disabled:opacity-50 transition-colors"
                >
                  {saving ? "Kaydediliyor…" : "Kaydet"}
                </button>
              </div>

              <div className="pt-4 border-t border-border divide-y divide-border">
                <div className="flex items-center justify-between py-2.5">
                  <span className="text-sm text-text-muted">E-posta</span>
                  <span className="text-sm font-medium text-text">{user?.email ?? "—"}</span>
                </div>
                <div className="flex items-center justify-between py-2.5">
                  <span className="text-sm text-text-muted">Rol</span>
                  <span className="text-sm font-medium text-text">Platform Yöneticisi</span>
                </div>
                <div className="flex items-center justify-between py-2.5">
                  <span className="text-sm text-text-muted">Son giriş</span>
                  <span className="text-sm font-medium text-text">{fmtDate(user?.last_login_at ?? null)}</span>
                </div>
              </div>
            </div>
          )}

          {tab === "security" && (
            <div className="space-y-4">
              <PasswordChangeForm accessToken={accessToken} mode="platform" onCompleted={handlePasswordChangeCompleted} />
              <MfaSetupCard
                accessToken={accessToken}
                mfaEnabled={user?.mfa_enabled ?? false}
                onChanged={() => accessToken && loadUser(accessToken)}
              />
            </div>
          )}

          {tab === "sessions" && (
            <div className="bg-surface border border-border rounded-2xl p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-sm font-semibold text-text">Aktif Oturumlar</h3>
                  <p className="text-xs text-text-muted mt-0.5">Bu hesapla giriş yapılmış cihaz ve tarayıcılar.</p>
                </div>
                {sessions.length > 0 && (
                  <button onClick={handleRevokeAll} className="text-xs text-danger hover:underline flex-shrink-0">
                    Tüm oturumları kapat
                  </button>
                )}
              </div>

              {sessionsLoading ? (
                <div className="space-y-2">
                  {Array.from({ length: 2 }).map((_, i) => <div key={i} className="h-14 bg-surface-2 rounded-lg animate-pulse" />)}
                </div>
              ) : sessions.length === 0 ? (
                <p className="text-sm text-text-muted opacity-60 text-center py-6">Aktif oturum bulunamadı.</p>
              ) : (
                <div className="space-y-2">
                  {sessions.map((s) => (
                    <div key={s.id} className="flex items-center justify-between bg-surface-2 border border-border rounded-xl px-4 py-3">
                      <div>
                        <p className="text-sm font-medium text-text">{parseDevice(s.user_agent)}</p>
                        <p className="text-xs text-text-muted mt-0.5">
                          {s.ip_address ?? "IP bilinmiyor"} · Oluşturulma: {fmtDate(s.created_at)}
                        </p>
                      </div>
                      <button
                        onClick={() => handleRevokeSession(s.id)}
                        disabled={revokingId === s.id}
                        className="text-xs text-danger hover:underline disabled:opacity-50 flex-shrink-0"
                      >
                        {revokingId === s.id ? "Kapatılıyor…" : "Oturumu kapat"}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

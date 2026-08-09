"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ApiError,
  platformApi,
  type PlatformUserRead,
  type PlatformUserDetail,
} from "@/lib/api-client";
import { platformAuthStorage } from "@/lib/platform-auth";

// ── Helpers ───────────────────────────────────────────────────────────────────

const USER_TYPE_LABELS: Record<string, string> = {
  platform_admin: "Platform Admin",
  agency_owner: "Ajans Sahibi",
  agency_manager: "Ajans Yöneticisi",
  agency_member: "Ajans Üyesi",
  agency_user: "Ajans Kullanıcısı",
  brand_contact: "Marka İletişim",
  brand_user: "Marka Kullanıcısı",
};

const USER_TYPE_COLORS: Record<string, string> = {
  platform_admin: "status-purple",
  agency_owner:   "status-accent",
  agency_manager: "status-info",
  agency_member:  "status-info",
  agency_user:    "status-info",
  brand_contact:  "status-warning",
  brand_user:     "status-warning",
};

function initials(name: string) {
  return name
    .split(" ")
    .map((w) => w[0] ?? "")
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("tr-TR", { day: "2-digit", month: "short", year: "numeric" });
}

// ── Sub-components ────────────────────────────────────────────────────────────

function TypeBadge({ type }: { type: string }) {
  const cls = USER_TYPE_COLORS[type] ?? "status-neutral";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${cls}`}>
      {USER_TYPE_LABELS[type] ?? type}
    </span>
  );
}

function StatusDot({ active }: { active: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${active ? "text-success" : "text-danger"}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${active ? "bg-success" : "bg-danger"}`} />
      {active ? "Aktif" : "Pasif"}
    </span>
  );
}

function SkeletonRow() {
  return (
    <tr className="border-b border-border">
      {[60, 80, 70, 50, 40, 30].map((w, i) => (
        <td key={i} className="px-5 py-4">
          <div className={`h-4 bg-surface-2 rounded animate-pulse w-${w === 30 ? "8" : w === 40 ? "10" : w === 50 ? "16" : w === 60 ? "24" : w === 70 ? "20" : "28"}`} />
        </td>
      ))}
    </tr>
  );
}

// ── User Detail Drawer ────────────────────────────────────────────────────────

interface DrawerProps {
  userId: string;
  onClose: () => void;
  onUpdated: (u: PlatformUserRead) => void;
}

function UserDrawer({ userId, onClose, onUpdated }: DrawerProps) {
  const [detail, setDetail] = useState<PlatformUserDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [terminating, setTerminating] = useState(false);
  const [editName, setEditName] = useState("");
  const [toast, setToast] = useState<{ type: "ok" | "err"; msg: string } | null>(null);

  useEffect(() => {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    platformApi.getUserDetail(userId, token).then((d) => {
      setDetail(d);
      setEditName(d.full_name);
    }).finally(() => setLoading(false));
  }, [userId]);

  function showToast(type: "ok" | "err", msg: string) {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3000);
  }

  async function handleSaveName() {
    const token = platformAuthStorage.getToken();
    if (!token || !detail) return;
    setSaving(true);
    try {
      const updated = await platformApi.updateUser(userId, { full_name: editName }, token);
      setDetail((d) => d ? { ...d, full_name: updated.full_name } : d);
      onUpdated(updated);
      showToast("ok", "Ad güncellendi.");
    } catch {
      showToast("err", "Kaydedilemedi.");
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleActive() {
    const token = platformAuthStorage.getToken();
    if (!token || !detail) return;
    setSaving(true);
    try {
      if (detail.is_active) {
        await platformApi.deactivateUser(userId, token);
        setDetail((d) => d ? { ...d, is_active: false } : d);
        onUpdated({ ...detail, is_active: false });
        showToast("ok", "Kullanıcı pasif edildi.");
      } else {
        await platformApi.reactivateUser(userId, token);
        setDetail((d) => d ? { ...d, is_active: true } : d);
        onUpdated({ ...detail, is_active: true });
        showToast("ok", "Kullanıcı aktif edildi.");
      }
    } catch {
      showToast("err", "İşlem başarısız.");
    } finally {
      setSaving(false);
    }
  }

  async function handleTerminate() {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setTerminating(true);
    try {
      await platformApi.terminateSessions(userId, token);
      showToast("ok", "Tüm oturumlar sonlandırıldı.");
    } catch {
      showToast("err", "Oturumlar sonlandırılamadı.");
    } finally {
      setTerminating(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="flex-1 bg-black/50" onClick={onClose} />
      <div className="w-[480px] bg-surface border-l border-border flex flex-col overflow-hidden shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="text-sm font-semibold text-text">Kullanıcı Detayı</h2>
          <button onClick={onClose} className="text-text-muted hover:text-text transition-colors">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {loading ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          </div>
        ) : !detail ? (
          <div className="flex-1 flex items-center justify-center text-sm text-text-muted">Yüklenemedi.</div>
        ) : (
          <div className="flex-1 overflow-y-auto">
            {/* Avatar + name */}
            <div className="px-6 py-5 border-b border-border">
              <div className="flex items-center gap-4 mb-4">
                <div className="w-12 h-12 rounded-full bg-accent-subtle border border-accent/30 flex items-center justify-center text-accent font-semibold text-sm flex-shrink-0">
                  {initials(detail.full_name)}
                </div>
                <div className="min-w-0">
                  <p className="font-semibold text-text truncate">{detail.full_name}</p>
                  <p className="text-xs text-text-muted truncate">{detail.email}</p>
                </div>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <TypeBadge type={detail.user_type} />
                <StatusDot active={detail.is_active} />
                {detail.is_verified && (
                  <span className="inline-flex items-center gap-1 text-xs text-success">
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                    Doğrulandı
                  </span>
                )}
                {detail.mfa_enabled && (
                  <span className="status-purple text-xs rounded px-1.5 py-0.5">MFA</span>
                )}
              </div>
            </div>

            {/* Toast */}
            {toast && (
              <div className={`mx-6 mt-4 rounded-lg px-4 py-2.5 text-xs font-medium ${toast.type === "ok" ? "status-success" : "status-danger"}`}>
                {toast.msg}
              </div>
            )}

            {/* İletişim & Bildirim */}
            <div className="px-6 py-4 border-b border-border">
              <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">İletişim & Bildirim</p>
              <div className="space-y-2.5">
                <div className="flex justify-between text-sm">
                  <span className="text-text-muted">Telefon</span>
                  <span className="text-text">{detail.phone_number ?? "—"}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-text-muted">WhatsApp onayı</span>
                  <span className={detail.whatsapp_opt_in ? "text-success" : "text-text-muted opacity-60"}>
                    {detail.whatsapp_opt_in ? "Açık" : "Kapalı"}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-text-muted">E-posta bildirimi</span>
                  <span className={detail.notification_email_enabled ? "text-success" : "text-text-muted opacity-60"}>
                    {detail.notification_email_enabled == null ? "—" : detail.notification_email_enabled ? "Açık" : "Kapalı"}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-text-muted">WhatsApp bildirimi</span>
                  <span className={detail.notification_whatsapp_enabled ? "text-success" : "text-text-muted opacity-60"}>
                    {detail.notification_whatsapp_enabled == null ? "—" : detail.notification_whatsapp_enabled ? "Açık" : "Kapalı"}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-text-muted">Uygulama içi</span>
                  <span className={detail.notification_in_app_enabled ? "text-success" : "text-text-muted opacity-60"}>
                    {detail.notification_in_app_enabled == null ? "—" : detail.notification_in_app_enabled ? "Açık" : "Kapalı"}
                  </span>
                </div>
              </div>
            </div>

            {/* Brief istatistikleri */}
            <div className="px-6 py-4 border-b border-border">
              <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Aktivite</p>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-surface-2 rounded-lg p-3 border border-border">
                  <p className="text-2xl font-bold text-text">{detail.brief_created_count}</p>
                  <p className="text-xs text-text-muted mt-0.5">Oluşturulan brief</p>
                </div>
                <div className="bg-surface-2 rounded-lg p-3 border border-border">
                  <p className="text-2xl font-bold text-text">{detail.brief_assigned_count}</p>
                  <p className="text-xs text-text-muted mt-0.5">Atanan brief</p>
                </div>
              </div>
              <div className="mt-3 flex justify-between text-sm">
                <span className="text-text-muted">Son giriş</span>
                <span className="text-text-secondary">{fmtDate(detail.last_login_at)}</span>
              </div>
              <div className="mt-2 flex justify-between text-sm">
                <span className="text-text-muted">Kayıt tarihi</span>
                <span className="text-text-secondary">{fmtDate(detail.created_at)}</span>
              </div>
            </div>

            {/* Ajans üyelikleri */}
            {detail.agency_memberships.length > 0 && (
              <div className="px-6 py-4 border-b border-border">
                <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Ajans Üyelikleri</p>
                <div className="space-y-2">
                  {detail.agency_memberships.map((m) => (
                    <div key={m.agency_id} className="flex items-center justify-between text-sm bg-surface-2 rounded-lg px-3 py-2 border border-border">
                      <span className="text-text font-medium">{m.agency_name}</span>
                      <span className="text-xs text-text-muted">{m.role}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Marka üyelikleri */}
            {detail.brand_memberships.length > 0 && (
              <div className="px-6 py-4 border-b border-border">
                <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Marka Üyelikleri</p>
                <div className="space-y-2">
                  {detail.brand_memberships.map((m) => (
                    <div key={m.brand_id} className="flex items-center justify-between text-sm bg-surface-2 rounded-lg px-3 py-2 border border-border">
                      <span className="text-text font-medium">{m.brand_name}</span>
                      <span className="text-xs text-text-muted">{m.role}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Ad düzenleme */}
            {detail.user_type !== "platform_admin" && (
              <div className="px-6 py-4 border-b border-border">
                <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Ad Düzenle</p>
                <div className="flex gap-2">
                  <input
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    className="flex-1 bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-accent"
                    placeholder="Kullanıcı adı"
                  />
                  <button
                    onClick={handleSaveName}
                    disabled={saving || editName === detail.full_name}
                    className="px-3 py-2 bg-accent hover:bg-accent-hover disabled:opacity-40 text-white text-xs font-medium rounded-lg transition-colors"
                  >
                    {saving ? "…" : "Kaydet"}
                  </button>
                </div>
              </div>
            )}

            {/* Aksiyon butonları */}
            {detail.user_type !== "platform_admin" && (
              <div className="px-6 py-4 space-y-2">
                <button
                  onClick={handleToggleActive}
                  disabled={saving}
                  className={`w-full py-2.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
                    detail.is_active
                      ? "status-danger hover:bg-danger/20"
                      : "status-success hover:bg-success/20"
                  }`}
                >
                  {detail.is_active ? "Kullanıcıyı Pasif Et" : "Kullanıcıyı Aktif Et"}
                </button>
                <button
                  onClick={handleTerminate}
                  disabled={terminating}
                  className="status-warning w-full py-2.5 rounded-lg text-sm font-medium hover:bg-warning/20 transition-colors disabled:opacity-50"
                >
                  {terminating ? "Sonlandırılıyor…" : "Tüm Oturumları Sonlandır"}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PlatformUsersPage() {
  const router = useRouter();
  const [users, setUsers] = useState<PlatformUserRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState("");
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  async function load(filter?: string, q?: string) {
    const token = platformAuthStorage.getToken();
    if (!token) { router.replace("/platform/login"); return; }
    setLoading(true);
    setError(null);
    try {
      const data = await platformApi.listUsersWithSearch(token, {
        user_type: filter || undefined,
        search: q || undefined,
        limit: 100,
      });
      setUsers(data);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        platformAuthStorage.clearAll();
        router.replace("/platform/login");
      } else {
        setError(err instanceof ApiError ? err.message : "Yükleme başarısız");
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(typeFilter, search); }, [typeFilter, search]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleSearchChange(val: string) {
    setSearchInput(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setSearch(val), 350);
  }

  function handleUserUpdated(updated: PlatformUserRead) {
    setUsers((prev) => prev.map((u) => (u.id === updated.id ? { ...u, ...updated } : u)));
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <p className="text-xs font-semibold text-accent uppercase tracking-wider mb-0.5">Platform Yönetimi</p>
          <h1 className="text-2xl font-bold text-text">Kullanıcılar</h1>
          <p className="text-sm text-text-muted mt-1">
            {loading ? "Yükleniyor…" : `${users.length} kullanıcı`}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-6">
        <div className="relative flex-1 max-w-xs">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            value={searchInput}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="İsim veya e-posta ara…"
            className="w-full pl-9 pr-4 py-2 bg-surface-2 border border-border rounded-lg text-sm text-text placeholder:text-text-placeholder focus:outline-none focus:border-accent transition-colors"
          />
        </div>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text-secondary focus:outline-none focus:border-accent transition-colors"
        >
          <option value="">Tüm Tipler</option>
          {Object.entries(USER_TYPE_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
      </div>

      {error && (
        <div className="mb-6 status-danger rounded-xl p-4 text-sm">
          {error}
        </div>
      )}

      {/* Table */}
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-surface-2">
              <th className="text-left px-5 py-3 text-xs font-semibold text-text-muted uppercase tracking-wider">Kullanıcı</th>
              <th className="text-left px-5 py-3 text-xs font-semibold text-text-muted uppercase tracking-wider">Tip</th>
              <th className="text-left px-5 py-3 text-xs font-semibold text-text-muted uppercase tracking-wider">MFA</th>
              <th className="text-left px-5 py-3 text-xs font-semibold text-text-muted uppercase tracking-wider">Son Giriş</th>
              <th className="text-left px-5 py-3 text-xs font-semibold text-text-muted uppercase tracking-wider">Durum</th>
              <th className="px-5 py-3" />
            </tr>
          </thead>
          <tbody>
            {loading && Array.from({ length: 8 }).map((_, i) => <SkeletonRow key={i} />)}
            {!loading && users.length === 0 && (
              <tr>
                <td colSpan={6} className="px-5 py-16 text-center text-text-muted">
                  <svg className="w-10 h-10 mx-auto mb-3 text-text-muted opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  Kullanıcı bulunamadı
                </td>
              </tr>
            )}
            {!loading && users.map((user) => (
              <tr
                key={user.id}
                className="border-b border-border hover:bg-surface-2 transition-colors cursor-pointer"
                onClick={() => setSelectedUserId(user.id)}
              >
                <td className="px-5 py-3.5">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-accent-subtle border border-accent/20 flex items-center justify-center text-accent text-xs font-semibold flex-shrink-0">
                      {initials(user.full_name)}
                    </div>
                    <div>
                      <p className="font-medium text-text text-sm">{user.full_name}</p>
                      <p className="text-xs text-text-muted">{user.email}</p>
                    </div>
                  </div>
                </td>
                <td className="px-5 py-3.5">
                  <TypeBadge type={user.user_type} />
                </td>
                <td className="px-5 py-3.5">
                  {user.mfa_enabled ? (
                    <span className="inline-flex items-center gap-1 text-xs text-success">
                      <span className="w-1.5 h-1.5 rounded-full bg-success" />
                      Aktif
                    </span>
                  ) : (
                    <span className="text-xs text-text-muted opacity-60">Kapalı</span>
                  )}
                </td>
                <td className="px-5 py-3.5 text-xs text-text-muted">{fmtDate(user.last_login_at)}</td>
                <td className="px-5 py-3.5">
                  <StatusDot active={user.is_active} />
                </td>
                <td className="px-5 py-3.5 text-right">
                  <button
                    onClick={(e) => { e.stopPropagation(); setSelectedUserId(user.id); }}
                    className="text-xs text-accent hover:text-accent-hover transition-colors"
                  >
                    Detay →
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedUserId && (
        <UserDrawer
          userId={selectedUserId}
          onClose={() => setSelectedUserId(null)}
          onUpdated={handleUserUpdated}
        />
      )}
    </div>
  );
}

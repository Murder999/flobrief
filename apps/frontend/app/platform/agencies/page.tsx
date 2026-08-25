"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ApiError,
  platformApi,
  type PlatformAgencyRead,
  type PlatformAgencyMemberRead,
  type PlatformAgencyDetail,
  type PlatformBrandRead,
  type PlatformBrandMemberRead,
  type AgencyBrandingRead,
  type CustomDomainRead,
  type PlanRead,
} from "@/lib/api-client";
import { platformAuthStorage } from "@/lib/platform-auth";
import { useLocale } from "@/context/locale-context";
import { ConfirmActionModal, type ConfirmActionDetails } from "@/components/platform/ConfirmActionModal";
import { MembershipRecoveryPanel } from "@/components/platform/MembershipRecoveryPanel";
import { AgencyProvisioningModal, BrandProvisioningModal } from "@/components/platform/ProvisioningModals";

// ── Role / permission matrix (mirrors app/core/rbac.py agency role sets) ───────

const ROLE_LABELS: Record<string, string> = {
  owner: "Sahip",
  admin: "Yönetici",
  brand_manager: "Marka Yöneticisi",
  designer: "Tasarımcı",
  developer: "Geliştirici",
  social_media_manager: "Sosyal Medya Yöneticisi",
  viewer: "İzleyici",
};

const PERMISSION_LABELS: [key: string, label: string][] = [
  ["brief_view", "Brief görüntüleme"],
  ["brief_create", "Brief oluşturma"],
  ["brief_update", "Brief düzenleme"],
  ["brief_submit_approval", "Onaya gönderme"],
  ["brand_manage", "Marka yönetimi"],
  ["member_manage", "Üye yönetimi"],
  ["calendar_manage", "Takvim yönetimi"],
  ["reporting_view", "Rapor görüntüleme"],
  ["billing_manage", "Faturalama erişimi"],
  ["white_label_manage", "Ayar yönetimi (white-label)"],
];

// Mirrors _AGENCY_ROLE_PERMISSIONS in app/core/rbac.py
const ROLE_PERMISSIONS: Record<string, Set<string>> = {
  owner: new Set(["brief_view", "brief_create", "brief_update", "brief_submit_approval", "brand_manage", "member_manage", "calendar_manage", "reporting_view", "billing_manage", "white_label_manage"]),
  admin: new Set(["brief_view", "brief_create", "brief_update", "brief_submit_approval", "brand_manage", "member_manage", "calendar_manage", "reporting_view", "billing_manage"]),
  brand_manager: new Set(["brief_view", "brief_create", "brief_update", "brief_submit_approval", "brand_manage", "calendar_manage", "reporting_view", "billing_manage"]),
  designer: new Set(["brief_view", "brief_create", "brief_update"]),
  developer: new Set(["brief_view"]),
  social_media_manager: new Set(["brief_view", "brief_create", "calendar_manage", "reporting_view"]),
  viewer: new Set(["brief_view"]),
};

const BRAND_ROLES = ["brand_owner", "brand_manager", "brand_viewer", "external_approver"];

function PermissionMatrix() {
  const roles = Object.keys(ROLE_LABELS);
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr>
            <th className="text-left px-2 py-2 text-text-muted font-medium">İzin</th>
            {roles.map((r) => (
              <th key={r} className="px-1.5 py-2 text-text-muted font-medium whitespace-nowrap">{ROLE_LABELS[r]}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {PERMISSION_LABELS.map(([key, label]) => (
            <tr key={key} className="border-t border-border/60">
              <td className="px-2 py-1.5 text-text-secondary whitespace-nowrap">{label}</td>
              {roles.map((r) => (
                <td key={r} className="px-1.5 py-1.5 text-center">
                  {ROLE_PERMISSIONS[r].has(key) ? (
                    <span className="inline-block w-2 h-2 rounded-full bg-success" title="Var" />
                  ) : (
                    <span className="inline-block w-2 h-2 rounded-full bg-border" title="Yok" />
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const STATUS_LABELS: Record<string, string> = {
  active: "Aktif",
  suspended: "Askıya Alındı",
  pending: "Beklemede",
  inactive: "Pasif",
};

const STATUS_COLORS: Record<string, string> = {
  active:    "status-success",
  suspended: "status-danger",
  pending:   "status-warning",
  inactive:  "status-neutral",
};

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("tr-TR", { day: "2-digit", month: "short", year: "numeric" });
}

function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_COLORS[status] ?? "status-neutral";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${cls} capitalize`}>
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

// ── Agency Detail Drawer ──────────────────────────────────────────────────────

interface AgencyDrawerProps {
  agency: PlatformAgencyRead;
  onClose: () => void;
  onUpdated: (a: PlatformAgencyRead) => void;
}

function AgencyDrawer({ agency, onClose, onUpdated }: AgencyDrawerProps) {
  const { t } = useLocale();
  const [detail, setDetail] = useState<PlatformAgencyDetail | null>(null);
  const [members, setMembers] = useState<PlatformAgencyMemberRead[]>([]);
  const [brands, setBrands] = useState<PlatformBrandRead[]>([]);
  const [branding, setBranding] = useState<AgencyBrandingRead | null>(null);
  const [domain, setDomain] = useState<CustomDomainRead | null>(null);
  const [plans, setPlans] = useState<PlanRead[]>([]);
  const [auditFeed, setAuditFeed] = useState<{ source: string; id: string; action: string; entity_type?: string; meta: Record<string, unknown> | null; created_at: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [editName, setEditName] = useState(agency.name);
  const [editStatus, setEditStatus] = useState(agency.status);
  const [saving, setSaving] = useState(false);
  const [suspendReason, setSuspendReason] = useState("");
  const [toast, setToast] = useState<{ type: "ok" | "err"; msg: string } | null>(null);
  const [tab, setTab] = useState<"genel" | "white_label" | "uyeler" | "plan" | "markalar" | "audit">("genel");
  const [memberSaving, setMemberSaving] = useState<string | null>(null);
  const [planSaving, setPlanSaving] = useState(false);
  const [showBrandProvisioning, setShowBrandProvisioning] = useState(false);
  const [pendingAction, setPendingAction] = useState<{
    details: ConfirmActionDetails;
    run: () => Promise<void>;
    destructive?: boolean;
  } | null>(null);

  useEffect(() => {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    Promise.all([
      platformApi.getAgency(agency.id, token),
      platformApi.getAgencyMembers(agency.id, token).catch(() => []),
      platformApi.getAgencyBrands(agency.id, token).catch(() => []),
      platformApi.getAgencyBrandingAdmin(agency.id, token).catch(() => null),
      platformApi.listPlans(token).catch(() => []),
      platformApi.getAgencyAuditFeed(agency.id, token).catch(() => []),
    ]).then(([d, m, b, brandingResp, planList, audit]) => {
      setDetail(d);
      setMembers(m);
      setBrands(b);
      setBranding(brandingResp?.branding ?? null);
      setDomain(brandingResp?.domain ?? null);
      setPlans(planList);
      setAuditFeed(audit);
    }).finally(() => setLoading(false));
  }, [agency.id]);

  function showToast(type: "ok" | "err", msg: string) {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3000);
  }

  async function handleMemberRoleChange(memberId: string, role: string) {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setMemberSaving(memberId);
    try {
      const updated = await platformApi.updateAgencyMember(agency.id, memberId, { role }, token);
      setMembers((prev) => prev.map((m) => (m.id === memberId ? { ...m, role: updated.role } : m)));
      showToast("ok", "Rol güncellendi.");
    } catch (err) {
      showToast("err", err instanceof ApiError ? err.message : "Rol güncellenemedi.");
    } finally {
      setMemberSaving(null);
    }
  }

  async function handleMemberStatusChange(memberId: string, status: string) {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setMemberSaving(memberId);
    try {
      const updated = await platformApi.updateAgencyMember(agency.id, memberId, { status }, token);
      setMembers((prev) => prev.map((m) => (m.id === memberId ? { ...m, status: updated.status } : m)));
      showToast("ok", "Durum güncellendi.");
    } catch (err) {
      showToast("err", err instanceof ApiError ? err.message : "Durum güncellenemedi.");
    } finally {
      setMemberSaving(null);
    }
  }

  async function handlePlanChange(planId: string) {
    const token = platformAuthStorage.getToken();
    if (!token || !detail) return;
    setPlanSaving(true);
    try {
      const updated = await platformApi.updateAgencyPlan(agency.id, planId, "Platform admin değişikliği", token);
      setDetail(updated);
      showToast("ok", "Plan güncellendi.");
    } catch (err) {
      showToast("err", err instanceof ApiError ? err.message : "Plan güncellenemedi.");
    } finally {
      setPlanSaving(false);
    }
  }

  async function handleSave() {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setSaving(true);
    try {
      const updated = await platformApi.updateAgency(agency.id, { name: editName, status: editStatus }, token);
      onUpdated(updated);
      showToast("ok", "Ajans güncellendi.");
    } catch {
      showToast("err", "Kaydedilemedi.");
    } finally {
      setSaving(false);
    }
  }

  async function handleSuspend() {
    const token = platformAuthStorage.getToken();
    if (!token || !suspendReason.trim()) return;
    setSaving(true);
    try {
      await platformApi.suspendAgency(agency.id, suspendReason, token);
      onUpdated({ ...agency, status: "suspended" });
      setEditStatus("suspended");
      showToast("ok", "Ajans askıya alındı.");
      setSuspendReason("");
    } catch {
      showToast("err", "Askıya alınamadı.");
    } finally {
      setSaving(false);
    }
  }

  async function handleReactivate() {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setSaving(true);
    try {
      await platformApi.reactivateAgency(agency.id, token);
      onUpdated({ ...agency, status: "active" });
      setEditStatus("active");
      showToast("ok", "Ajans aktif edildi.");
    } catch {
      showToast("err", "Aktif edilemedi.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="flex-1 bg-black/50" onClick={onClose} />
      <div className="w-full sm:max-w-[520px] bg-surface border-l border-border flex flex-col overflow-hidden shadow-2xl">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div>
            <p className="text-xs text-text-muted mb-0.5">Ajans</p>
            <h2 className="text-sm font-semibold text-text">{agency.name}</h2>
          </div>
          <button onClick={onClose} className="text-text-muted hover:text-text-secondary transition-colors">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-border overflow-x-auto">
          {(["genel", "white_label", "uyeler", "plan", "markalar", "audit"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-3 text-xs font-semibold uppercase tracking-wider transition-colors whitespace-nowrap ${tab === t ? "text-accent border-b-2 border-accent" : "text-text-muted hover:text-text-secondary"}`}
            >
              {t === "genel" ? "Genel Bakış"
                : t === "white_label" ? "White Label"
                : t === "uyeler" ? `Kullanıcılar (${members.length})`
                : t === "plan" ? "Plan & Limitler"
                : t === "markalar" ? `Markalar (${brands.length})`
                : "Aktivite & Audit"}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto">
            {toast && (
              <div className={`mx-6 mt-4 rounded-lg px-4 py-2.5 text-xs font-medium ${toast.type === "ok" ? "status-success" : "status-danger"}`}>
                {toast.msg}
              </div>
            )}

            {tab === "genel" && (
              <div className="px-6 py-5 space-y-5">
                {/* Stats */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-surface-2 border border-border rounded-xl p-3 text-center">
                    <p className="text-xl font-bold text-text">{agency.member_count}</p>
                    <p className="text-xs text-text-muted mt-0.5">Üye</p>
                  </div>
                  <div className="bg-surface-2 border border-border rounded-xl p-3 text-center">
                    <p className="text-xl font-bold text-text">{agency.brand_count}</p>
                    <p className="text-xs text-text-muted mt-0.5">Marka</p>
                  </div>
                  <div className="bg-surface-2 border border-border rounded-xl p-3 text-center">
                    <StatusBadge status={agency.status} />
                    <p className="text-xs text-text-muted mt-1">Durum</p>
                  </div>
                </div>

                {/* Abonelik */}
                {detail && (detail.plan_name || detail.subscription_status) && (
                  <div>
                    <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Abonelik</p>
                    <div className="bg-surface-2 border border-border rounded-xl px-4 py-3 space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-text-muted">Plan</span>
                        <span className="text-text">{detail.plan_name ?? "—"}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-text-muted">Durum</span>
                        <span className="text-text">{detail.subscription_status ?? "—"}</span>
                      </div>
                      {detail.monthly_price_cents != null && (
                        <div className="flex justify-between">
                          <span className="text-text-muted">Aylık ücret</span>
                          <span className="text-text">${(detail.monthly_price_cents / 100).toFixed(2)}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Bilgi */}
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-text-muted">Slug</span>
                    <span className="text-text-secondary font-mono text-xs">{agency.slug}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-text-muted">Oluşturulma</span>
                    <span className="text-text-secondary">{fmtDate(agency.created_at)}</span>
                  </div>
                </div>

                {/* Düzenleme */}
                <div>
                  <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Düzenle</p>
                  <div className="space-y-2">
                    <input
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-accent"
                      placeholder="Ajans adı"
                    />
                    <button
                      onClick={handleSave}
                      disabled={saving || (editName === agency.name)}
                      className="w-full py-2 bg-accent hover:bg-accent-hover disabled:opacity-40 text-white text-sm font-medium rounded-lg transition-colors"
                    >
                      {saving ? "Kaydediliyor…" : "Değişiklikleri Kaydet"}
                    </button>
                  </div>
                </div>

                {/* Askıya al / aktif et */}
                {agency.status === "active" ? (
                  <div>
                    <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Askıya Al</p>
                    <textarea
                      value={suspendReason}
                      onChange={(e) => setSuspendReason(e.target.value)}
                      rows={2}
                      placeholder="Sebep yazın…"
                      className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text placeholder:text-text-placeholder focus:outline-none focus:border-danger resize-none mb-2"
                    />
                    <button
                      onClick={() => setPendingAction({
                        details: { action: t("platform.confirm.suspend"), agency: agency.name },
                        run: handleSuspend,
                        destructive: true,
                      })}
                      disabled={!suspendReason.trim() || saving}
                      className="w-full py-2 status-danger hover:bg-danger/20 text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
                    >
                      Ajansı Askıya Al
                    </button>
                  </div>
                ) : agency.status === "suspended" ? (
                  <button
                    onClick={() => setPendingAction({
                      details: { action: t("platform.confirm.reactivate"), agency: agency.name },
                      run: handleReactivate,
                    })}
                    disabled={saving}
                    className="w-full py-2 status-success hover:bg-success/20 text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
                  >
                    Ajansı Aktif Et
                  </button>
                ) : null}
              </div>
            )}

            {tab === "uyeler" && (
              <div className="px-6 py-5 space-y-5">
                {members.length === 0 ? (
                  <p className="text-sm text-text-muted opacity-60 text-center py-8">Üye bulunamadı.</p>
                ) : (
                  <div className="space-y-2">
                    {members.map((m) => (
                      <div key={m.id} className="bg-surface-2 border border-border rounded-xl px-4 py-3">
                        <div className="flex items-center justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-text truncate">{m.user_full_name}</p>
                            <p className="text-xs text-text-muted truncate">{m.user_email}</p>
                            {m.joined_at && (
                              <p className="text-xs text-text-muted opacity-60 mt-1">Katılım: {fmtDate(m.joined_at)}</p>
                            )}
                          </div>
                          <div className="flex items-center gap-2 flex-shrink-0">
                            <select
                              value={m.role}
                              disabled={memberSaving === m.id}
                              onChange={(e) => {
                                const role = e.target.value;
                                e.target.value = m.role;
                                setPendingAction({
                                  details: { action: t("platform.confirm.changeRole"), agency: agency.name, user: m.user_email ?? undefined, role },
                                  run: () => handleMemberRoleChange(m.id, role),
                                });
                              }}
                              className="bg-surface border border-border rounded-lg px-2 py-1.5 text-xs text-text-secondary focus:outline-none focus:border-accent disabled:opacity-50"
                            >
                              {Object.entries(ROLE_LABELS).map(([v, label]) => (
                                <option key={v} value={v}>{label}</option>
                              ))}
                            </select>
                            {m.status === "suspended" ? (
                              <button
                                disabled={memberSaving === m.id}
                                onClick={() => setPendingAction({
                                  details: { action: t("platform.confirm.changeStatus"), agency: agency.name, user: m.user_email ?? undefined, role: "active" },
                                  run: () => handleMemberStatusChange(m.id, "active"),
                                })}
                                className="text-xs px-2 py-1.5 rounded-lg status-success disabled:opacity-50"
                              >
                                Aktive Et
                              </button>
                            ) : (
                              <button
                                disabled={memberSaving === m.id}
                                onClick={() => setPendingAction({
                                  details: { action: t("platform.confirm.changeStatus"), agency: agency.name, user: m.user_email ?? undefined, role: "suspended" },
                                  run: () => handleMemberStatusChange(m.id, "suspended"),
                                  destructive: true,
                                })}
                                className="text-xs px-2 py-1.5 rounded-lg status-danger disabled:opacity-50"
                              >
                                Askıya Al
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <MembershipRecoveryPanel
                  onMemberAdded={(member) => {
                    setMembers((items) => [...items, member as PlatformAgencyMemberRead]);
                    onUpdated({ ...agency, member_count: agency.member_count + 1 });
                  }}
                  target={{ type: "agency", id: agency.id, agencyName: agency.name }}
                />

                <div>
                  <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">
                    İzin Matrisi (Referans)
                  </p>
                  <div className="bg-surface-2 border border-border rounded-xl p-3">
                    <PermissionMatrix />
                  </div>
                </div>
              </div>
            )}

            {tab === "white_label" && (
              <div className="px-6 py-5 space-y-4">
                {!branding ? (
                  <p className="text-sm text-text-muted opacity-60 text-center py-8">Yüklenemedi.</p>
                ) : (
                  <>
                    <div className="flex items-center justify-between bg-surface-2 border border-border rounded-xl px-4 py-3">
                      <span className="text-sm text-text-secondary">White-label durumu</span>
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-md ${branding.is_white_label_enabled ? "status-success" : "status-neutral"}`}>
                        {branding.is_white_label_enabled ? "Aktif" : "Kapalı"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between bg-surface-2 border border-border rounded-xl px-4 py-3">
                      <span className="text-sm text-text-secondary">Plan hakkı (entitlement)</span>
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-md ${branding.white_label_entitlement ? "status-success" : "status-warning"}`}>
                        {branding.white_label_entitlement ? "Var" : "Yok"}
                      </span>
                    </div>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-text-muted">Marka adı</span>
                        <span className="text-text-secondary">{branding.brand_name_override ?? "—"}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-text-muted">Renkler</span>
                        <div className="flex items-center gap-1.5">
                          {[branding.primary_color, branding.secondary_color, branding.accent_color].filter(Boolean).map((c) => (
                            <span key={c} className="w-4 h-4 rounded border border-border" style={{ background: c as string }} title={c as string} />
                          ))}
                          {!branding.primary_color && <span className="text-text-secondary">—</span>}
                        </div>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-text-muted">Logo</span>
                        <span className="text-text-secondary">{branding.logo_url ? "Yüklendi" : "—"}</span>
                      </div>
                    </div>
                    <div className="pt-3 border-t border-border">
                      <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Özel Domain</p>
                      {domain ? (
                        <div className="bg-surface-2 border border-border rounded-xl px-4 py-3 flex items-center justify-between">
                          <span className="text-sm font-mono text-text-secondary">{domain.domain}</span>
                          <span className={`text-xs font-medium px-2 py-0.5 rounded-md ${
                            domain.status === "verified" ? "status-success" : domain.status === "failed" ? "status-danger" : "status-warning"
                          }`}>
                            {domain.status === "verified" ? "Doğrulandı" : domain.status === "failed" ? "Başarısız" : domain.status === "disabled" ? "Devre Dışı" : "Bekliyor"}
                          </span>
                        </div>
                      ) : (
                        <p className="text-sm text-text-muted opacity-60">Yapılandırılmamış.</p>
                      )}
                    </div>
                    <p className="text-xs text-text-muted opacity-60 pt-2">
                      Bu ajansın kendi portal ayarlarındaki white-label yapılandırması salt-okunur gösterilir.
                      Platform genelindeki varsayılan marka ayarları için White Label bölümüne bakın.
                    </p>
                  </>
                )}
              </div>
            )}

            {tab === "plan" && (
              <div className="px-6 py-5 space-y-4">
                {detail && (
                  <div className="bg-surface-2 border border-border rounded-xl px-4 py-3 space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-text-muted">Mevcut plan</span>
                      <span className="text-text font-medium">{detail.plan_name ?? "—"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-text-muted">Abonelik durumu</span>
                      <span className="text-text-secondary">{detail.subscription_status ?? "—"}</span>
                    </div>
                    {detail.monthly_price_cents != null && (
                      <div className="flex justify-between">
                        <span className="text-text-muted">Aylık ücret</span>
                        <span className="text-text-secondary">${(detail.monthly_price_cents / 100).toFixed(2)}</span>
                      </div>
                    )}
                  </div>
                )}
                <div>
                  <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Plan Değiştir</p>
                  <div className="space-y-2">
                    {plans.map((p) => (
                      <button
                        key={p.id}
                        disabled={planSaving || detail?.plan_code === p.code}
                        onClick={() => handlePlanChange(p.id)}
                        className={`w-full text-left px-4 py-3 rounded-xl border transition-colors disabled:opacity-50 ${
                          detail?.plan_code === p.code ? "border-accent bg-accent/10" : "border-border bg-surface-2 hover:border-accent/50"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-text">{p.name}</span>
                          <span className="text-xs text-text-muted">${(p.monthly_price_cents / 100).toFixed(0)}/ay</span>
                        </div>
                        <p className="text-xs text-text-muted mt-1">
                          {p.max_brands ?? "Sınırsız"} marka · {p.max_users ?? "Sınırsız"} kullanıcı
                          {p.white_label_enabled && " · White-label"}
                        </p>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {tab === "audit" && (
              <div className="px-6 py-5">
                {auditFeed.length === 0 ? (
                  <p className="text-sm text-text-muted opacity-60 text-center py-8">Aktivite bulunamadı.</p>
                ) : (
                  <div className="space-y-2">
                    {auditFeed.map((e) => (
                      <div key={e.id} className="bg-surface-2 border border-border rounded-xl px-4 py-3">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-text">{e.action}</span>
                          <span className={`text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded ${e.source === "platform_admin" ? "text-accent bg-accent/10" : "text-text-muted bg-surface"}`}>
                            {e.source === "platform_admin" ? "Platform" : "Ajans"}
                          </span>
                        </div>
                        <p className="text-xs text-text-muted opacity-60 mt-1">{fmtDate(e.created_at)}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {tab === "markalar" && (
              <div className="px-6 py-5">
                <button
                  className="mb-4 w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-accent-hover"
                  onClick={() => setShowBrandProvisioning(true)}
                  type="button"
                >
                  {t("platform.provision.newBrand")}
                </button>
                {brands.length === 0 ? (
                  <p className="text-sm text-text-muted opacity-60 text-center py-8">Marka bulunamadı.</p>
                ) : (
                  <div className="space-y-2">
                    {brands.map((b) => (
                      <div key={b.id} className="bg-surface-2 border border-border rounded-xl px-4 py-3">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm font-medium text-text">{b.name}</p>
                            <p className="text-xs text-text-muted opacity-60 font-mono">{b.slug}</p>
                          </div>
                          <div className="text-right">
                            <StatusBadge status={b.status} />
                            <p className="text-xs text-text-muted mt-1">{b.member_count} üye · {b.brief_count} brief</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
      <ConfirmActionModal
        destructive={pendingAction?.destructive}
        details={pendingAction?.details ?? { action: "" }}
        loading={saving || memberSaving !== null}
        onClose={() => setPendingAction(null)}
        onConfirm={() => {
          if (!pendingAction) return;
          void pendingAction.run().finally(() => setPendingAction(null));
        }}
        open={Boolean(pendingAction)}
      />
      {showBrandProvisioning && (
        <BrandProvisioningModal
          agencies={[agency]}
          onClose={() => setShowBrandProvisioning(false)}
          onCreated={({ brand }) => {
            setBrands((items) => [brand, ...items]);
            onUpdated({ ...agency, brand_count: agency.brand_count + 1 });
            setShowBrandProvisioning(false);
          }}
        />
      )}
    </div>
  );
}

// ── Brand Detail Drawer ───────────────────────────────────────────────────────

interface BrandDrawerProps {
  brand: PlatformBrandRead;
  onClose: () => void;
  onUpdated: (b: PlatformBrandRead) => void;
}

function BrandDrawer({ brand, onClose, onUpdated }: BrandDrawerProps) {
  const { t } = useLocale();
  const [members, setMembers] = useState<PlatformBrandMemberRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [editName, setEditName] = useState(brand.name);
  const [editStatus, setEditStatus] = useState(brand.status);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ type: "ok" | "err"; msg: string } | null>(null);
  const [memberSaving, setMemberSaving] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<{
    details: ConfirmActionDetails;
    run: () => Promise<void>;
    destructive?: boolean;
  } | null>(null);

  useEffect(() => {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    platformApi.getBrandMembers(brand.id, token).then(setMembers).catch(() => {}).finally(() => setLoading(false));
  }, [brand.id]);

  function showToast(type: "ok" | "err", msg: string) {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3000);
  }

  async function handleSave() {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setSaving(true);
    try {
      const updated = await platformApi.updateBrandPlatform(brand.id, { name: editName, status: editStatus }, token);
      onUpdated(updated);
      showToast("ok", "Marka güncellendi.");
    } catch {
      showToast("err", "Kaydedilemedi.");
    } finally {
      setSaving(false);
    }
  }

  async function handleMemberUpdate(memberId: string, change: { role?: string; status?: string }) {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setMemberSaving(memberId);
    try {
      const updated = await platformApi.updateBrandMember(brand.id, memberId, change, token);
      setMembers((items) => items.map((member) => member.id === memberId ? updated : member));
      showToast("ok", change.role ? "Rol güncellendi." : "Durum güncellendi.");
    } catch (err) {
      showToast("err", err instanceof ApiError ? err.message : "Üye güncellenemedi.");
    } finally {
      setMemberSaving(null);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="flex-1 bg-black/50" onClick={onClose} />
      <div className="w-full sm:max-w-[520px] bg-surface border-l border-border flex flex-col overflow-hidden shadow-2xl">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div>
            <p className="text-xs text-text-muted mb-0.5">Marka</p>
            <h2 className="text-sm font-semibold text-text">{brand.name}</h2>
          </div>
          <button onClick={onClose} className="text-text-muted hover:text-text-secondary transition-colors">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          <div className="px-6 py-5 border-b border-border">
            <div className="grid grid-cols-3 gap-3 mb-4">
              <div className="bg-surface-2 border border-border rounded-xl p-3 text-center">
                <p className="text-xl font-bold text-text">{brand.member_count}</p>
                <p className="text-xs text-text-muted mt-0.5">Üye</p>
              </div>
              <div className="bg-surface-2 border border-border rounded-xl p-3 text-center">
                <p className="text-xl font-bold text-text">{brand.brief_count}</p>
                <p className="text-xs text-text-muted mt-0.5">Brief</p>
              </div>
              <div className="bg-surface-2 border border-border rounded-xl p-3 text-center">
                <StatusBadge status={brand.status} />
                <p className="text-xs text-text-muted mt-1">Durum</p>
              </div>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-text-muted">Ajans</span>
                <span className="text-text-secondary">{brand.agency_name ?? "—"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-muted">Slug</span>
                <span className="text-text-secondary font-mono text-xs">{brand.slug}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-muted">Oluşturulma</span>
                <span className="text-text-secondary">{fmtDate(brand.created_at)}</span>
              </div>
            </div>
          </div>

          {toast && (
            <div className={`mx-6 mt-4 rounded-lg px-4 py-2.5 text-xs font-medium ${toast.type === "ok" ? "status-success" : "status-danger"}`}>
              {toast.msg}
            </div>
          )}

          {/* Düzenle */}
          <div className="px-6 py-5 border-b border-border">
            <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Düzenle</p>
            <div className="space-y-2">
              <input
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-accent"
                placeholder="Marka adı"
              />
              <select
                value={editStatus}
                onChange={(e) => setEditStatus(e.target.value)}
                className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text-secondary focus:outline-none focus:border-accent"
              >
                <option value="active">Aktif</option>
                <option value="inactive">Pasif</option>
                <option value="suspended">Askıya Alındı</option>
              </select>
              <button
                onClick={() => setPendingAction({
                  details: { action: t("platform.confirm.changeStatus"), agency: brand.agency_name ?? undefined, brand: brand.name, role: editStatus },
                  run: handleSave,
                  destructive: editStatus !== "active",
                })}
                disabled={saving || (editName === brand.name && editStatus === brand.status)}
                className="w-full py-2 bg-accent hover:bg-accent-hover disabled:opacity-40 text-white text-sm font-medium rounded-lg transition-colors"
              >
                {saving ? "Kaydediliyor…" : "Değişiklikleri Kaydet"}
              </button>
            </div>
          </div>

          {/* Üyeler */}
          <div className="px-6 py-5">
            <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Üyeler ({members.length})</p>
            {loading ? (
              <div className="text-center py-4 text-text-muted opacity-60 text-sm">Yükleniyor…</div>
            ) : members.length === 0 ? (
              <p className="text-sm text-text-muted opacity-60 text-center py-4">Üye bulunamadı.</p>
            ) : (
              <div className="space-y-2">
                {members.map((m) => (
                  <div key={m.id} className="bg-surface-2 border border-border rounded-xl px-4 py-3">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-text">{m.user_full_name}</p>
                        <p className="truncate text-xs text-text-muted">{m.user_email}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <select
                          className="rounded-lg border border-border bg-surface px-2 py-1.5 text-xs text-text-secondary"
                          disabled={memberSaving === m.id}
                          onChange={(event) => {
                            const role = event.target.value;
                            event.target.value = m.role;
                            setPendingAction({
                              details: { action: t("platform.confirm.changeRole"), agency: brand.agency_name ?? undefined, brand: brand.name, user: m.user_email ?? undefined, role },
                              run: () => handleMemberUpdate(m.id, { role }),
                            });
                          }}
                          value={m.role}
                        >
                          {BRAND_ROLES.map((role) => <option key={role} value={role}>{role}</option>)}
                        </select>
                        <button
                          className={`rounded-lg px-2 py-1.5 text-xs font-medium ${m.status === "active" ? "status-danger" : "status-success"}`}
                          disabled={memberSaving === m.id}
                          onClick={() => {
                            const status = m.status === "active" ? "suspended" : "active";
                            setPendingAction({
                              details: { action: t("platform.confirm.changeStatus"), agency: brand.agency_name ?? undefined, brand: brand.name, user: m.user_email ?? undefined, role: status },
                              run: () => handleMemberUpdate(m.id, { status }),
                              destructive: status === "suspended",
                            });
                          }}
                          type="button"
                        >
                          {m.status === "active" ? "Askıya Al" : "Aktive Et"}
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <div className="mt-5">
              <MembershipRecoveryPanel
                onMemberAdded={(member) => {
                  setMembers((items) => [...items, member as PlatformBrandMemberRead]);
                  onUpdated({ ...brand, member_count: brand.member_count + 1 });
                }}
                target={{ type: "brand", id: brand.id, agencyName: brand.agency_name ?? undefined, brandName: brand.name }}
              />
            </div>
          </div>
        </div>
      </div>
      <ConfirmActionModal
        destructive={pendingAction?.destructive}
        details={pendingAction?.details ?? { action: "" }}
        loading={saving || memberSaving !== null}
        onClose={() => setPendingAction(null)}
        onConfirm={() => {
          if (!pendingAction) return;
          void pendingAction.run().finally(() => setPendingAction(null));
        }}
        open={Boolean(pendingAction)}
      />
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PlatformAgenciesPage() {
  const router = useRouter();
  const { t } = useLocale();

  // Tab
  const [activeTab, setActiveTab] = useState<"ajanslar" | "markalar">("ajanslar");

  // Agency state
  const [agencies, setAgencies] = useState<PlatformAgencyRead[]>([]);
  const [agencyLoading, setAgencyLoading] = useState(true);
  const [agencyError, setAgencyError] = useState<string | null>(null);
  const [agencyStatusFilter, setAgencyStatusFilter] = useState("");
  const [selectedAgency, setSelectedAgency] = useState<PlatformAgencyRead | null>(null);
  const [showAgencyProvisioning, setShowAgencyProvisioning] = useState(false);

  // Brand state
  const [brands, setBrands] = useState<PlatformBrandRead[]>([]);
  const [brandLoading, setBrandLoading] = useState(true);
  const [brandError, setBrandError] = useState<string | null>(null);
  const [brandSearch, setBrandSearch] = useState("");
  const [brandSearchInput, setBrandSearchInput] = useState("");
  const [brandStatusFilter, setBrandStatusFilter] = useState("");
  const [selectedBrand, setSelectedBrand] = useState<PlatformBrandRead | null>(null);
  const [showBrandProvisioning, setShowBrandProvisioning] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  async function loadAgencies(filter?: string) {
    const token = platformAuthStorage.getToken();
    if (!token) { router.replace("/platform/login"); return; }
    setAgencyLoading(true);
    setAgencyError(null);
    try {
      const data = await platformApi.listAgencies(token, { status_filter: filter || undefined, limit: 100 });
      setAgencies(data);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) { platformAuthStorage.clearAll(); router.replace("/platform/login"); }
      else setAgencyError(err instanceof ApiError ? err.message : "Yükleme başarısız");
    } finally {
      setAgencyLoading(false);
    }
  }

  async function loadBrands(q?: string, statusF?: string) {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setBrandLoading(true);
    setBrandError(null);
    try {
      const data = await platformApi.listBrands(token, { search: q || undefined, status_filter: statusF || undefined, limit: 100 });
      setBrands(data);
    } catch (err) {
      setBrandError(err instanceof ApiError ? err.message : "Yükleme başarısız");
    } finally {
      setBrandLoading(false);
    }
  }

  useEffect(() => { loadAgencies(agencyStatusFilter); }, [agencyStatusFilter]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { loadBrands(brandSearch, brandStatusFilter); }, [brandSearch, brandStatusFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleBrandSearchChange(val: string) {
    setBrandSearchInput(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setBrandSearch(val), 350);
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      {/* Header */}
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold text-accent uppercase tracking-wider mb-0.5">Platform Yönetimi</p>
          <h1 className="text-2xl font-bold text-text">Ajanslar & Markalar</h1>
          <p className="text-sm text-text-muted mt-1">Platformdaki tüm ajans ve markaları yönetin.</p>
        </div>
        <button
          className="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-accent-hover sm:w-auto"
          data-testid="new-tenant-button"
          onClick={() => activeTab === "ajanslar" ? setShowAgencyProvisioning(true) : setShowBrandProvisioning(true)}
          type="button"
        >
          {activeTab === "ajanslar" ? t("platform.provision.newAgency") : t("platform.provision.newBrand")}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-6 bg-surface-2 border border-border rounded-xl p-1 w-fit">
        <button
          data-testid="platform-tab-agencies"
          onClick={() => setActiveTab("ajanslar")}
          className={`px-5 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === "ajanslar" ? "bg-surface text-text shadow-sm" : "text-text-muted hover:text-text"}`}
        >
          Ajanslar {!agencyLoading && `(${agencies.length})`}
        </button>
        <button
          data-testid="platform-tab-brands"
          onClick={() => setActiveTab("markalar")}
          className={`px-5 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === "markalar" ? "bg-surface text-text shadow-sm" : "text-text-muted hover:text-text"}`}
        >
          Markalar {!brandLoading && `(${brands.length})`}
        </button>
      </div>

      {/* Ajanslar tab */}
      {activeTab === "ajanslar" && (
        <>
          <div className="flex flex-wrap items-center gap-3 mb-5">
            <select
              value={agencyStatusFilter}
              onChange={(e) => setAgencyStatusFilter(e.target.value)}
              className="bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text-secondary focus:outline-none focus:border-accent transition-colors"
            >
              <option value="">Tüm Durumlar</option>
              <option value="active">Aktif</option>
              <option value="suspended">Askıya Alındı</option>
              <option value="pending">Beklemede</option>
            </select>
          </div>

          {agencyError && (
            <div className="mb-5 status-danger rounded-xl p-4 text-sm">{agencyError}</div>
          )}

          <div className="bg-surface border border-border rounded-xl overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-border bg-surface-2">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-text-muted uppercase tracking-wider">Ajans</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-text-muted uppercase tracking-wider">Durum</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-text-muted uppercase tracking-wider">Üye</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-text-muted uppercase tracking-wider">Marka</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-text-muted uppercase tracking-wider">Oluşturulma</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody>
                {agencyLoading && Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i} className="border-b border-border">
                    {Array.from({ length: 6 }).map((__, j) => (
                      <td key={j} className="px-5 py-4"><div className="h-4 bg-surface-2 rounded animate-pulse" /></td>
                    ))}
                  </tr>
                ))}
                {!agencyLoading && agencies.length === 0 && (
                  <tr><td colSpan={6} className="px-5 py-16 text-center text-text-muted opacity-60">Ajans bulunamadı.</td></tr>
                )}
                {!agencyLoading && agencies.map((agency) => (
                  <tr
                    key={agency.id}
                    className="border-b border-border/50 hover:bg-surface-2 transition-colors cursor-pointer"
                    onClick={() => setSelectedAgency(agency)}
                  >
                    <td className="px-5 py-3.5">
                      <p className="font-medium text-text">{agency.name}</p>
                      <p className="text-xs text-text-muted opacity-60 font-mono mt-0.5">{agency.slug}</p>
                    </td>
                    <td className="px-5 py-3.5"><StatusBadge status={agency.status} /></td>
                    <td className="px-5 py-3.5 text-text-muted">{agency.member_count}</td>
                    <td className="px-5 py-3.5 text-text-muted">{agency.brand_count}</td>
                    <td className="px-5 py-3.5 text-xs text-text-muted">{fmtDate(agency.created_at)}</td>
                    <td className="px-5 py-3.5 text-right">
                      <button className="text-xs text-accent hover:text-accent-hover transition-colors">Detay →</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Markalar tab */}
      {activeTab === "markalar" && (
        <>
          <div className="flex flex-col gap-3 mb-5 sm:flex-row sm:items-center">
            <div className="relative flex-1 sm:max-w-xs">
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                value={brandSearchInput}
                onChange={(e) => handleBrandSearchChange(e.target.value)}
                placeholder="Marka ara…"
                className="w-full pl-9 pr-4 py-2 bg-surface-2 border border-border rounded-lg text-sm text-text placeholder:text-text-placeholder focus:outline-none focus:border-accent transition-colors"
              />
            </div>
            <select
              value={brandStatusFilter}
              onChange={(e) => setBrandStatusFilter(e.target.value)}
              className="bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text-secondary focus:outline-none focus:border-accent transition-colors"
            >
              <option value="">Tüm Durumlar</option>
              <option value="active">Aktif</option>
              <option value="inactive">Pasif</option>
              <option value="suspended">Askıya Alındı</option>
            </select>
          </div>

          {brandError && (
            <div className="mb-5 status-danger rounded-xl p-4 text-sm">{brandError}</div>
          )}

          <div className="bg-surface border border-border rounded-xl overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-border bg-surface-2">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-text-muted uppercase tracking-wider">Marka</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-text-muted uppercase tracking-wider">Ajans</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-text-muted uppercase tracking-wider">Durum</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-text-muted uppercase tracking-wider">Üye</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-text-muted uppercase tracking-wider">Brief</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody>
                {brandLoading && Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i} className="border-b border-border">
                    {Array.from({ length: 6 }).map((__, j) => (
                      <td key={j} className="px-5 py-4"><div className="h-4 bg-surface-2 rounded animate-pulse" /></td>
                    ))}
                  </tr>
                ))}
                {!brandLoading && brands.length === 0 && (
                  <tr><td colSpan={6} className="px-5 py-16 text-center text-text-muted opacity-60">Marka bulunamadı.</td></tr>
                )}
                {!brandLoading && brands.map((brand) => (
                  <tr
                    key={brand.id}
                    className="border-b border-border/50 hover:bg-surface-2 transition-colors cursor-pointer"
                    onClick={() => setSelectedBrand(brand)}
                  >
                    <td className="px-5 py-3.5">
                      <p className="font-medium text-text">{brand.name}</p>
                      <p className="text-xs text-text-muted opacity-60 font-mono mt-0.5">{brand.slug}</p>
                    </td>
                    <td className="px-5 py-3.5 text-text-muted text-xs">{brand.agency_name ?? "—"}</td>
                    <td className="px-5 py-3.5"><StatusBadge status={brand.status} /></td>
                    <td className="px-5 py-3.5 text-text-muted">{brand.member_count}</td>
                    <td className="px-5 py-3.5 text-text-muted">{brand.brief_count}</td>
                    <td className="px-5 py-3.5 text-right">
                      <button className="text-xs text-accent hover:text-accent-hover transition-colors">Detay →</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Drawers */}
      {selectedAgency && (
        <AgencyDrawer
          agency={selectedAgency}
          onClose={() => setSelectedAgency(null)}
          onUpdated={(updated) => {
            setAgencies((prev) => prev.map((a) => (a.id === updated.id ? { ...a, ...updated } : a)));
            setSelectedAgency((prev) => prev ? { ...prev, ...updated } : prev);
          }}
        />
      )}
      {selectedBrand && (
        <BrandDrawer
          brand={selectedBrand}
          onClose={() => setSelectedBrand(null)}
          onUpdated={(updated) => {
            setBrands((prev) => prev.map((b) => (b.id === updated.id ? { ...b, ...updated } : b)));
            setSelectedBrand((prev) => prev ? { ...prev, ...updated } : prev);
          }}
        />
      )}
      {showAgencyProvisioning && (
        <AgencyProvisioningModal
          onClose={() => setShowAgencyProvisioning(false)}
          onCreated={({ agency }) => {
            setAgencies((items) => [agency, ...items]);
            setShowAgencyProvisioning(false);
            setSelectedAgency(agency);
          }}
        />
      )}
      {showBrandProvisioning && (
        <BrandProvisioningModal
          agencies={agencies.filter((agency) => agency.status === "active")}
          onClose={() => setShowBrandProvisioning(false)}
          onCreated={({ brand }) => {
            setBrands((items) => [brand, ...items]);
            setShowBrandProvisioning(false);
            setSelectedBrand(brand);
          }}
        />
      )}
    </div>
  );
}

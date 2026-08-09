"use client";

import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { ownerApi, invitationApi } from "@/lib/api-client";
import { useToast } from "@/components/ui/toast";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, useMemo } from "react";

interface OwnerMember {
  member_id: string;
  user_id: string;
  full_name: string;
  email: string;
  role: string;
  status: string;
  last_login_at: string | null;
  joined_at: string | null;
  created_at: string;
}

const ROLE_LABELS: Record<string, string> = {
  owner: "Sahip",
  admin: "Yönetici",
  brand_manager: "Marka Yöneticisi",
  designer: "Tasarımcı",
  developer: "Geliştirici",
  social_media_manager: "Sosyal Medya",
  viewer: "Görüntüleyici",
};

const STATUS_STYLES: Record<string, string> = {
  active: "bg-success/10 text-success border-success/20",
  invited: "bg-warning/10 text-warning border-warning/20",
  suspended: "bg-danger/10 text-danger border-danger/20",
};

const STATUS_LABELS: Record<string, string> = {
  active: "Aktif",
  invited: "Davetli",
  suspended: "Askıda",
};

function getInitials(name: string): string {
  return name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("tr-TR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function SkeletonRow() {
  return (
    <tr className="animate-pulse">
      <td className="px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-surface-2 flex-shrink-0" />
          <div>
            <div className="h-3 bg-surface-2 rounded w-32 mb-1.5" />
            <div className="h-2.5 bg-surface-2 rounded w-44" />
          </div>
        </div>
      </td>
      <td className="px-6 py-4"><div className="h-5 bg-surface-2 rounded-full w-20" /></td>
      <td className="px-6 py-4"><div className="h-5 bg-surface-2 rounded-full w-16" /></td>
      <td className="px-6 py-4"><div className="h-3 bg-surface-2 rounded w-24" /></td>
      <td className="px-6 py-4"><div className="h-3 bg-surface-2 rounded w-24" /></td>
      <td className="px-6 py-4"><div className="h-7 bg-surface-2 rounded-lg w-20" /></td>
    </tr>
  );
}

export default function OwnerMembersPage() {
  const { accessToken, user } = useAuth();
  const { activeAgency, isInitialized } = useWorkspace();
  const router = useRouter();
  const { toast, confirm } = useToast();
  const [members, setMembers] = useState<OwnerMember[] | null>(null);
  const [deactivating, setDeactivating] = useState<string | null>(null);
  const [reinviting, setReinviting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [roleFilter, setRoleFilter] = useState<string>("all");

  const load = () => {
    if (!accessToken || !activeAgency?.id) return;
    ownerApi
      .members(activeAgency.id, accessToken)
      .then(setMembers)
      .catch(() => setError("Üyeler yüklenirken hata oluştu."));
  };

  useEffect(() => {
    if (!isInitialized) return;
    if (activeAgency && activeAgency.member_role !== "owner") {
      router.replace("/dashboard");
      return;
    }
    load();
  }, [accessToken, activeAgency?.id, isInitialized]); // eslint-disable-line react-hooks/exhaustive-deps

  const filteredMembers = useMemo(() => {
    if (!members) return null;
    return members.filter((m) => {
      const matchSearch =
        !search ||
        m.full_name.toLowerCase().includes(search.toLowerCase()) ||
        m.email.toLowerCase().includes(search.toLowerCase());
      const matchStatus = statusFilter === "all" || m.status === statusFilter;
      const matchRole = roleFilter === "all" || m.role === roleFilter;
      return matchSearch && matchStatus && matchRole;
    });
  }, [members, search, statusFilter, roleFilter]);

  const handleDeactivate = async (member: OwnerMember) => {
    const ok = await confirm({
      title: "Üyeyi Askıya Al",
      message: `${member.full_name} adlı üyeyi askıya almak istediğinizden emin misiniz? Bu kişi platforma erişimini kaybeder.`,
      confirmLabel: "Askıya Al",
      cancelLabel: "İptal",
      destructive: true,
    });
    if (!ok) return;

    setDeactivating(member.member_id);
    try {
      await ownerApi.deactivateMember(member.member_id, activeAgency!.id, accessToken!);
      toast(`${member.full_name} askıya alındı.`, "success");
      load();
    } catch {
      toast("İşlem başarısız. Lütfen tekrar deneyin.", "error");
    } finally {
      setDeactivating(null);
    }
  };

  const handleReinvite = async (member: OwnerMember) => {
    setReinviting(member.member_id);
    try {
      await invitationApi.inviteAgencyMember(
        activeAgency!.id,
        { email: member.email, role: member.role },
        accessToken!
      );
      toast(`${member.email} adresine davet yeniden gönderildi.`, "success");
    } catch {
      toast("Davet gönderilemedi. Lütfen tekrar deneyin.", "error");
    } finally {
      setReinviting(null);
    }
  };

  const uniqueRoles = members ? [...new Set(members.map((m) => m.role))] : [];

  return (
    <div className="p-4 sm:p-8 max-w-6xl mx-auto">
      <div className="flex items-center gap-3 mb-8">
        <Link
          href="/dashboard/owner"
          className="p-2 rounded-lg hover:bg-surface-2 transition-colors text-text-muted"
          title="Sahip paneline dön"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-text">Ekip Üyeleri</h1>
          <p className="text-sm text-text-muted mt-0.5">
            {members ? `${members.length} üye` : "Yükleniyor…"}
          </p>
        </div>
        <Link
          href="/dashboard/settings/members"
          className="inline-flex items-center gap-2 px-4 py-2 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent-hover transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Üye Davet Et
        </Link>
      </div>

      {error && (
        <div className="mb-6 px-4 py-3 bg-danger/10 border border-danger/20 rounded-xl text-sm text-danger">
          {error}
        </div>
      )}

      {/* Search + filters */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-3 mb-4">
        <div className="relative flex-1 sm:max-w-sm">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="İsim veya e-posta ile ara…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 h-9 bg-surface border border-border rounded-lg text-sm text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
          />
        </div>
        <div className="flex items-center gap-3">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-9 px-3 flex-1 sm:flex-none bg-surface border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
          >
            <option value="all">Tüm Durumlar</option>
            <option value="active">Aktif</option>
            <option value="invited">Davetli</option>
            <option value="suspended">Askıda</option>
          </select>
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="h-9 px-3 flex-1 sm:flex-none bg-surface border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
          >
            <option value="all">Tüm Roller</option>
            {uniqueRoles.map((r) => (
              <option key={r} value={r}>{ROLE_LABELS[r] ?? r}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Desktop table */}
      <div className="hidden md:block bg-surface border border-border rounded-2xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border bg-surface-2/30">
              <th className="text-left px-6 py-3 text-xs font-semibold text-text-muted uppercase tracking-wide">Üye</th>
              <th className="text-left px-6 py-3 text-xs font-semibold text-text-muted uppercase tracking-wide">Rol</th>
              <th className="text-left px-6 py-3 text-xs font-semibold text-text-muted uppercase tracking-wide">Durum</th>
              <th className="text-left px-6 py-3 text-xs font-semibold text-text-muted uppercase tracking-wide">Son Giriş</th>
              <th className="text-left px-6 py-3 text-xs font-semibold text-text-muted uppercase tracking-wide">Katılım</th>
              <th className="px-6 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {filteredMembers === null ? (
              <>
                <SkeletonRow />
                <SkeletonRow />
                <SkeletonRow />
                <SkeletonRow />
              </>
            ) : filteredMembers.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-16 text-center">
                  <div className="flex flex-col items-center gap-2">
                    <svg className="w-8 h-8 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                    </svg>
                    <p className="text-sm font-medium text-text">Üye bulunamadı</p>
                    <p className="text-xs text-text-muted">Arama kriterlerini değiştirmeyi deneyin.</p>
                  </div>
                </td>
              </tr>
            ) : (
              filteredMembers.map((m) => (
                <tr key={m.member_id} className="hover:bg-surface-2/40 transition-colors">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 bg-accent/15 rounded-full flex items-center justify-center flex-shrink-0">
                        <span className="text-xs font-semibold text-accent">{getInitials(m.full_name)}</span>
                      </div>
                      <div>
                        <p className="text-sm font-medium text-text">{m.full_name}</p>
                        <p className="text-xs text-text-muted">{m.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-surface-2 text-text-muted border border-border">
                      {ROLE_LABELS[m.role] ?? m.role}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${STATUS_STYLES[m.status] ?? "bg-surface-2 text-text-muted border-border"}`}
                    >
                      <span className="w-1.5 h-1.5 rounded-full mr-1.5 bg-current opacity-70" />
                      {STATUS_LABELS[m.status] ?? m.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-text-muted">{formatDate(m.last_login_at)}</td>
                  <td className="px-6 py-4 text-sm text-text-muted">{formatDate(m.joined_at ?? m.created_at)}</td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      {m.status === "invited" && (
                        <button
                          onClick={() => handleReinvite(m)}
                          disabled={reinviting === m.member_id}
                          className="px-3 py-1.5 text-xs font-medium text-accent hover:bg-accent/10 border border-accent/30 rounded-lg transition-colors disabled:opacity-50"
                        >
                          {reinviting === m.member_id ? "…" : "Yeniden Davet"}
                        </button>
                      )}
                      {m.status !== "suspended" && m.user_id !== user?.id && (
                        <button
                          onClick={() => handleDeactivate(m)}
                          disabled={deactivating === m.member_id}
                          className="px-3 py-1.5 text-xs font-medium text-danger hover:bg-danger/10 border border-danger/20 rounded-lg transition-colors disabled:opacity-50"
                        >
                          {deactivating === m.member_id ? "…" : "Askıya Al"}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Mobile cards — the table above is clipped (not scrollable) at 390px,
          so mobile gets a distinct card list instead of a shrunk table. */}
      <div className="md:hidden flex flex-col gap-3">
        {filteredMembers === null ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 bg-surface-2 rounded-xl animate-pulse" />
          ))
        ) : filteredMembers.length === 0 ? (
          <div className="bg-surface border border-border rounded-2xl px-6 py-16 text-center">
            <p className="text-sm font-medium text-text mb-1">Üye bulunamadı</p>
            <p className="text-xs text-text-muted">Arama kriterlerini değiştirmeyi deneyin.</p>
          </div>
        ) : (
          filteredMembers.map((m) => (
            <div key={m.member_id} className="bg-surface border border-border rounded-xl p-4">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 bg-accent/15 rounded-full flex items-center justify-center flex-shrink-0">
                  <span className="text-xs font-semibold text-accent">{getInitials(m.full_name)}</span>
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-text truncate">{m.full_name}</p>
                  <p className="text-xs text-text-muted truncate">{m.email}</p>
                </div>
                <span
                  className={`flex-shrink-0 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${STATUS_STYLES[m.status] ?? "bg-surface-2 text-text-muted border-border"}`}
                >
                  <span className="w-1.5 h-1.5 rounded-full mr-1.5 bg-current opacity-70" />
                  {STATUS_LABELS[m.status] ?? m.status}
                </span>
              </div>
              <div className="flex items-center gap-2 mt-3 text-xs text-text-muted">
                <span className="inline-flex items-center px-2 py-0.5 rounded bg-surface-2 border border-border font-medium text-text-secondary">
                  {ROLE_LABELS[m.role] ?? m.role}
                </span>
                <span>Son giriş: {formatDate(m.last_login_at)}</span>
              </div>
              {(m.status === "invited" || (m.status !== "suspended" && m.user_id !== user?.id)) && (
                <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border">
                  {m.status === "invited" && (
                    <button
                      onClick={() => handleReinvite(m)}
                      disabled={reinviting === m.member_id}
                      className="flex-1 px-3 py-2 text-xs font-medium text-accent hover:bg-accent/10 border border-accent/30 rounded-lg transition-colors disabled:opacity-50"
                    >
                      {reinviting === m.member_id ? "…" : "Yeniden Davet"}
                    </button>
                  )}
                  {m.status !== "suspended" && m.user_id !== user?.id && (
                    <button
                      onClick={() => handleDeactivate(m)}
                      disabled={deactivating === m.member_id}
                      className="flex-1 px-3 py-2 text-xs font-medium text-danger hover:bg-danger/10 border border-danger/20 rounded-lg transition-colors disabled:opacity-50"
                    >
                      {deactivating === m.member_id ? "…" : "Askıya Al"}
                    </button>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </div>

      <p className="mt-4 text-xs text-text-muted">
        Yeni üye davetlemek için{" "}
        <Link href="/dashboard/settings/members" className="text-accent hover:underline">
          Ekip Ayarları
        </Link>{" "}
        sayfasını kullanın.
      </p>
    </div>
  );
}

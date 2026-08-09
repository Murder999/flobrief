"use client";

import { useAuth } from "@/hooks/useAuth";
import {
  brandPortalApi,
  ApiError,
  type BrandTeamResponse,
  type BrandTeamUsage,
} from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { useCallback, useEffect, useState } from "react";
import { UserPlus, Mail, X, RotateCw, ShieldAlert, Users } from "lucide-react";

const ROLE_OPTIONS = [
  { value: "brand_manager", label: "Marka Yöneticisi" },
  { value: "brand_viewer", label: "Görüntüleyici (yorum yapabilir)" },
  { value: "external_approver", label: "Onay Yetkilisi" },
];

const ROLE_LABELS: Record<string, string> = {
  brand_owner: "Marka Sahibi",
  brand_manager: "Marka Yöneticisi",
  brand_viewer: "Görüntüleyici",
  external_approver: "Onay Yetkilisi",
};

function TeamSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="h-24 bg-surface-2 rounded-xl" />
      <div className="h-40 bg-surface-2 rounded-xl" />
      <div className="h-52 bg-surface-2 rounded-xl" />
    </div>
  );
}

export default function BrandTeamPage() {
  const { accessToken } = useAuth();
  const { toast, confirm } = useToast();

  const [team, setTeam] = useState<BrandTeamResponse | null>(null);
  const [usage, setUsage] = useState<BrandTeamUsage | null>(null);
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);

  const [email, setEmail] = useState("");
  const [role, setRole] = useState("brand_viewer");
  const [message, setMessage] = useState("");
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [busyInviteId, setBusyInviteId] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setForbidden(false);
    try {
      const [teamData, usageData] = await Promise.all([
        brandPortalApi.getTeam(accessToken),
        brandPortalApi.getTeamUsage(accessToken),
      ]);
      setTeam(teamData);
      setUsage(usageData);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setForbidden(true);
      } else {
        toast("Ekip bilgileri yüklenemedi", "error");
      }
    } finally {
      setLoading(false);
    }
  }, [accessToken, toast]);

  useEffect(() => {
    load();
  }, [load]);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!accessToken) return;
    setInviteError(null);

    if (!email.trim() || !email.includes("@")) {
      setInviteError("Geçerli bir e-posta adresi girin");
      return;
    }

    setSubmitting(true);
    try {
      await brandPortalApi.inviteTeamMember(
        { email: email.trim(), role, message: message.trim() || null },
        accessToken
      );
      toast("Davet gönderildi", "success");
      setEmail("");
      setMessage("");
      await load();
    } catch (err) {
      if (err instanceof ApiError) {
        const detail = err.detail as { message?: string } | string | undefined;
        const msg = typeof detail === "object" && detail?.message ? detail.message : err.message;
        setInviteError(msg);
      } else {
        setInviteError("Davet gönderilemedi");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = async (invitationId: string) => {
    if (!accessToken) return;
    const ok = await confirm({
      title: "Daveti iptal et",
      message: "Bu davet iptal edilecek. Emin misiniz?",
      confirmLabel: "İptal Et",
      destructive: true,
    });
    if (!ok) return;
    setBusyInviteId(invitationId);
    try {
      await brandPortalApi.cancelTeamInvitation(invitationId, accessToken);
      toast("Davet iptal edildi", "success");
      await load();
    } catch {
      toast("Davet iptal edilemedi", "error");
    } finally {
      setBusyInviteId(null);
    }
  };

  const handleResend = async (invitationId: string) => {
    if (!accessToken) return;
    setBusyInviteId(invitationId);
    try {
      await brandPortalApi.resendTeamInvitation(invitationId, accessToken);
      toast("Davet yeniden gönderildi", "success");
      await load();
    } catch {
      toast("Davet yeniden gönderilemedi", "error");
    } finally {
      setBusyInviteId(null);
    }
  };

  if (loading) {
    return <div className="p-8 max-w-4xl mx-auto"><TeamSkeleton /></div>;
  }

  if (forbidden) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <div className="flex flex-col items-center justify-center py-20 text-center bg-surface border border-border rounded-xl">
          <div className="w-14 h-14 bg-surface-2 rounded-2xl flex items-center justify-center mb-4">
            <ShieldAlert className="w-6 h-6 text-text-muted" />
          </div>
          <p className="text-base font-medium text-text">Bu sayfaya erişiminiz yok</p>
          <p className="text-sm text-text-muted mt-1">Ekip yönetimi yalnızca marka yöneticisine açıktır.</p>
        </div>
      </div>
    );
  }

  const seatsAvailable = usage?.users.available;
  const seatsFull = usage?.users.limit !== null && (seatsAvailable ?? 1) <= 0;

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-text">Ekip</h1>
        <p className="text-sm text-text-muted mt-1">Marka ekibinizi yönetin ve yeni üyeler davet edin.</p>
      </div>

      {/* Quota card */}
      {usage && (
        <div className="bg-surface border border-border rounded-xl p-5 flex items-center gap-6">
          <div className="w-11 h-11 rounded-xl bg-accent-subtle flex items-center justify-center flex-shrink-0">
            <Users className="w-5 h-5 text-accent" />
          </div>
          <div className="flex-1 grid grid-cols-2 sm:grid-cols-3 gap-4">
            <div>
              <p className="text-xs text-text-muted">Kullanıcılar</p>
              <p className="text-sm font-semibold text-text">
                {usage.users.used} / {usage.users.limit ?? "sınırsız"}
              </p>
            </div>
            <div>
              <p className="text-xs text-text-muted">Bekleyen davet</p>
              <p className="text-sm font-semibold text-text">{usage.users.pending_invites}</p>
            </div>
            <div>
              <p className="text-xs text-text-muted">Kullanılabilir koltuk</p>
              <p className={`text-sm font-semibold ${seatsFull ? "text-danger" : "text-text"}`}>
                {seatsAvailable ?? "sınırsız"}
              </p>
            </div>
          </div>
          {usage.plan_name && <Badge variant="accent">{usage.plan_name}</Badge>}
        </div>
      )}

      {/* Invite form */}
      <form onSubmit={handleInvite} className="bg-surface border border-border rounded-xl p-5 space-y-4">
        <h2 className="text-sm font-semibold text-text flex items-center gap-2">
          <UserPlus className="w-4 h-4 text-accent" />
          Yeni üye davet et
        </h2>
        {seatsFull && (
          <div className="px-3 py-2 rounded-lg bg-warning/10 border border-warning/30 text-xs text-warning">
            Kullanıcı limitine ulaşıldı ({usage?.users.used}/{usage?.users.limit}). Davet göndermek için planınızı yükseltin.
          </div>
        )}
        <div className="grid sm:grid-cols-2 gap-3">
          <Input
            label="E-posta"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="ornek@marka.com"
            error={inviteError ?? undefined}
          />
          <Select label="Rol" value={role} onChange={(e) => setRole(e.target.value)} options={ROLE_OPTIONS} />
        </div>
        <Input
          label="Mesaj (isteğe bağlı)"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Davete eklemek istediğiniz not"
        />
        <Button type="submit" disabled={submitting || seatsFull}>
          <Mail className="w-4 h-4" />
          {submitting ? "Gönderiliyor…" : "Davet Gönder"}
        </Button>
      </form>

      {/* Members */}
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <h2 className="text-sm font-semibold text-text px-5 py-4 border-b border-border">
          Ekip Üyeleri ({team?.members.length ?? 0})
        </h2>
        {!team?.members.length ? (
          <p className="px-5 py-8 text-center text-sm text-text-muted">Henüz ekip üyesi yok.</p>
        ) : (
          team.members.map((m) => (
            <div key={m.id} className="flex items-center justify-between px-5 py-3 border-b border-border last:border-0">
              <div>
                <p className="text-sm font-medium text-text">{m.full_name || m.email}</p>
                <p className="text-xs text-text-muted">{m.email}</p>
              </div>
              <Badge variant="default">{ROLE_LABELS[m.role] ?? m.role}</Badge>
            </div>
          ))
        )}
      </div>

      {/* Pending invitations */}
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <h2 className="text-sm font-semibold text-text px-5 py-4 border-b border-border">
          Bekleyen Davetler ({team?.pending_invitations.length ?? 0})
        </h2>
        {!team?.pending_invitations.length ? (
          <p className="px-5 py-8 text-center text-sm text-text-muted">Bekleyen davet yok.</p>
        ) : (
          team.pending_invitations.map((inv) => (
            <div key={inv.id} className="flex items-center justify-between px-5 py-3 border-b border-border last:border-0">
              <div>
                <p className="text-sm font-medium text-text">{inv.email}</p>
                <p className="text-xs text-text-muted">
                  {ROLE_LABELS[inv.role] ?? inv.role} · {new Date(inv.expires_at).toLocaleDateString("tr-TR")} tarihine kadar geçerli
                </p>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => handleResend(inv.id)}
                  disabled={busyInviteId === inv.id}
                  className="p-1.5 rounded-lg text-text-muted hover:text-accent hover:bg-hover transition-colors disabled:opacity-50"
                  title="Yeniden gönder"
                >
                  <RotateCw className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => handleCancel(inv.id)}
                  disabled={busyInviteId === inv.id}
                  className="p-1.5 rounded-lg text-text-muted hover:text-danger hover:bg-hover transition-colors disabled:opacity-50"
                  title="İptal et"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

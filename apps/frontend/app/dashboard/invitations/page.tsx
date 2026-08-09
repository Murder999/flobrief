"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { invitationApi, type InvitationRead } from "@/lib/api-client";

const ROLE_LABEL: Record<string, string> = {
  owner: "Sahip",
  admin: "Yönetici",
  brand_manager: "Marka Yöneticisi",
  designer: "Tasarımcı",
  developer: "Geliştirici",
  social_media_manager: "Sosyal Medya Yöneticisi",
  viewer: "İzleyici",
  brand_owner: "Marka Sahibi",
  brand_viewer: "Marka İzleyicisi",
  external_approver: "Harici Onaylayıcı",
};

function RoleBadge({ role }: { role: string }) {
  return (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-accent/15 text-accent border border-accent/20">
      {ROLE_LABEL[role] ?? role}
    </span>
  );
}

function TypeBadge({ type }: { type: string }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
        type === "brand"
          ? "bg-purple-500/10 text-purple-400 border border-purple-500/20"
          : "bg-blue-500/10 text-blue-400 border border-blue-500/20"
      }`}
    >
      {type === "brand" ? "Marka" : "Ajans"}
    </span>
  );
}

function formatExpiry(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays <= 0) return "Bugün sona eriyor";
  if (diffDays === 1) return "Yarın sona eriyor";
  return `${diffDays} gün içinde sona eriyor`;
}

function SkeletonCard() {
  return (
    <div className="bg-surface rounded-xl border border-border p-5 animate-pulse space-y-3">
      <div className="flex items-center justify-between">
        <div className="h-4 bg-surface-2 rounded w-1/3" />
        <div className="h-5 bg-surface-2 rounded-full w-16" />
      </div>
      <div className="h-3 bg-surface-2 rounded w-1/4" />
      <div className="flex gap-2 pt-2">
        <div className="h-9 bg-surface-2 rounded-lg flex-1" />
        <div className="h-9 bg-surface-2 rounded-lg flex-1" />
      </div>
    </div>
  );
}

interface InviteCardProps {
  invite: InvitationRead;
  onAccepted: (id: string) => void;
  onRejected: (id: string) => void;
}

function InviteCard({ invite, onAccepted, onRejected }: InviteCardProps) {
  const { accessToken } = useAuth();
  const [accepting, setAccepting] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [error, setError] = useState("");

  const handleAccept = async () => {
    if (!accessToken) return;
    setAccepting(true);
    setError("");
    try {
      await invitationApi.acceptById(invite.id, accessToken);
      onAccepted(invite.id);
    } catch (err: unknown) {
      const e = err as { message?: string };
      setError(e?.message ?? "Kabul edilemedi.");
    } finally {
      setAccepting(false);
    }
  };

  const handleReject = async () => {
    if (!accessToken) return;
    setRejecting(true);
    setError("");
    try {
      await invitationApi.reject(invite.id, accessToken);
      onRejected(invite.id);
    } catch (err: unknown) {
      const e = err as { message?: string };
      setError(e?.message ?? "Reddedilemedi.");
    } finally {
      setRejecting(false);
    }
  };

  return (
    <div className="bg-surface rounded-xl border border-border p-5 space-y-3 hover:border-accent/30 transition-colors">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-accent/15 border border-accent/20 flex items-center justify-center flex-shrink-0">
            <span className="text-xs font-bold text-accent">
              {invite.agency_id.slice(0, 1).toUpperCase()}
            </span>
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-text truncate">
              {invite.email}
            </p>
            <p className="text-xs text-text-muted">{formatExpiry(invite.expires_at)}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <TypeBadge type={invite.invitation_type} />
          <RoleBadge role={invite.role} />
        </div>
      </div>

      {error && (
        <p className="text-xs text-red-500 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      <div className="flex gap-2 pt-1">
        <button
          onClick={handleAccept}
          disabled={accepting || rejecting}
          className="flex-1 py-2 rounded-lg text-sm font-semibold bg-accent hover:bg-accent-hover text-white transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {accepting ? (
            <span className="flex items-center justify-center gap-1.5">
              <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
              </svg>
              Kabul ediliyor…
            </span>
          ) : (
            "Kabul Et"
          )}
        </button>
        <button
          onClick={handleReject}
          disabled={accepting || rejecting}
          className="flex-1 py-2 rounded-lg text-sm font-medium border border-border text-text-muted hover:border-red-400/50 hover:text-red-500 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {rejecting ? "Reddediliyor…" : "Reddet"}
        </button>
      </div>
    </div>
  );
}

export default function InvitationsPage() {
  const { accessToken } = useAuth();
  const [invitations, setInvitations] = useState<InvitationRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadInvitations = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const data = await invitationApi.getMyPending(accessToken);
      setInvitations(data);
    } catch {
      setError("Davetler yüklenemedi.");
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    loadInvitations();
  }, [loadInvitations]);

  const handleAccepted = (id: string) => {
    setInvitations((prev) => prev.filter((i) => i.id !== id));
  };

  const handleRejected = (id: string) => {
    setInvitations((prev) => prev.filter((i) => i.id !== id));
  };

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <div className="mb-8">
        <h1 className="text-xl font-semibold text-text">Davetlerim</h1>
        <p className="text-sm text-text-muted mt-1">
          Bekleyen davetlerinizi kabul edebilir veya reddedebilirsiniz.
        </p>
      </div>

      {loading && (
        <div className="space-y-4">
          {Array.from({ length: 2 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      )}

      {!loading && error && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/10 px-5 py-4 text-sm text-red-400">
          {error}
          <button
            onClick={loadInvitations}
            className="ml-3 underline hover:no-underline"
          >
            Tekrar dene
          </button>
        </div>
      )}

      {!loading && !error && invitations.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="w-16 h-16 rounded-full bg-surface border border-border flex items-center justify-center mb-4">
            <svg
              className="w-7 h-7 text-text-muted"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
              />
            </svg>
          </div>
          <h3 className="text-base font-semibold text-text mb-1">Bekleyen davetiniz yok</h3>
          <p className="text-sm text-text-muted max-w-xs">
            Bir ekibe davet edildiğinizde burada görünecek.
          </p>
        </div>
      )}

      {!loading && !error && invitations.length > 0 && (
        <div className="space-y-4">
          {invitations.map((invite) => (
            <InviteCard
              key={invite.id}
              invite={invite}
              onAccepted={handleAccepted}
              onRejected={handleRejected}
            />
          ))}
        </div>
      )}
    </div>
  );
}

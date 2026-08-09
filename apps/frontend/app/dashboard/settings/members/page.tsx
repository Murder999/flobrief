"use client";

import { useState, useEffect, useCallback } from "react";
import { agencyApi, invitationApi, type AgencyMemberRead, type InvitationRead } from "@/lib/api-client";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { Button } from "@/components/ui/button";
import { RoleBadge } from "@/components/team/role-badge";
import { InviteModal } from "@/components/team/invite-modal";

function SkeletonRow() {
  return (
    <div className="flex items-center gap-4 px-6 py-4 border-b border-border last:border-0">
      <div className="w-9 h-9 bg-surface-2 rounded-full animate-pulse flex-shrink-0" />
      <div className="flex-1 space-y-1.5">
        <div className="h-3.5 bg-surface-2 rounded w-32 animate-pulse" />
        <div className="h-3 bg-surface-2 rounded w-48 animate-pulse" />
      </div>
      <div className="h-5 bg-surface-2 rounded w-16 animate-pulse" />
    </div>
  );
}

export default function MembersPage() {
  const { user, accessToken } = useAuth();
  const { activeAgency, isLoading: workspaceLoading, isInitialized: workspaceReady } = useWorkspace();

  const [members, setMembers] = useState<AgencyMemberRead[]>([]);
  const [invitations, setInvitations] = useState<InvitationRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [tab, setTab] = useState<"members" | "invitations">("members");

  const loadData = useCallback(async () => {
    if (!activeAgency || !accessToken) return;

    setIsLoading(true);
    try {
      const [mems, invs] = await Promise.all([
        agencyApi.listMembers(activeAgency.id, accessToken),
        invitationApi.listAgencyInvitations(activeAgency.id, accessToken),
      ]);
      setMembers(mems);
      setInvitations(invs);
    } finally {
      setIsLoading(false);
    }
  }, [activeAgency, accessToken]);

  useEffect(() => {
    if (workspaceReady && !workspaceLoading && !activeAgency) {
      setIsLoading(false);
    }
  }, [workspaceReady, workspaceLoading, activeAgency]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRevoke = async (invitationId: string) => {
    if (!activeAgency || !accessToken) return;
    await invitationApi.revokeById(invitationId, activeAgency.id, accessToken);
    setInvitations((prev) => prev.filter((inv) => inv.id !== invitationId));
  };

  const handleResend = async (invitationId: string) => {
    if (!activeAgency || !accessToken) return;
    await invitationApi.resendById(invitationId, activeAgency.id, accessToken);
  };

  const canManageMembers =
    activeAgency?.member_role === "owner" || activeAgency?.member_role === "admin";

  const pendingCount = invitations.filter((i) => i.is_pending).length;

  if (!isLoading && !activeAgency) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-10 flex flex-col items-center justify-center py-20 text-center">
        <div className="w-14 h-14 bg-surface-2 rounded-2xl flex items-center justify-center mb-4">
          <span className="text-2xl">◓</span>
        </div>
        <p className="text-base font-medium text-text">Ajans seçilmedi</p>
        <p className="text-sm text-text-muted mt-1 mb-4">Ekibi yönetmek için bir ajans seçin.</p>
        <a href="/onboarding/create-agency" className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors">Ajans Oluştur</a>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-text">Ekip Yönetimi</h1>
          <p className="mt-1 text-sm text-text-muted">
            Ajansınızın ekip üyelerini yönetin.
          </p>
        </div>
        {canManageMembers && (
          <Button onClick={() => setShowInviteModal(true)}>
            + Üye Davet Et
          </Button>
        )}
      </div>

      <div className="flex gap-1 p-1 bg-surface-2 rounded-xl mb-6 w-fit">
        {(["members", "invitations"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${
              tab === t
                ? "bg-surface shadow-sm text-text"
                : "text-text-muted hover:text-text"
            }`}
          >
            {t === "members" ? "Üyeler" : "Davetler"}
            {t === "invitations" && pendingCount > 0 && (
              <span className="ml-1.5 inline-flex items-center justify-center w-4 h-4 bg-accent text-white text-xs rounded-full">
                {pendingCount}
              </span>
            )}
          </button>
        ))}
      </div>

      <div className="bg-surface border border-border rounded-2xl overflow-hidden">
        {tab === "members" && (
          <>
            {isLoading ? (
              Array.from({ length: 3 }).map((_, i) => <SkeletonRow key={i} />)
            ) : members.length === 0 ? (
              <div className="px-6 py-12 text-center">
                <p className="text-sm text-text-muted">Henüz üye yok.</p>
              </div>
            ) : (
              members.map((member) => (
                <div
                  key={member.id}
                  className="flex items-center gap-4 px-6 py-4 border-b border-border last:border-0"
                >
                  <div className="w-9 h-9 bg-accent/20 rounded-full flex items-center justify-center flex-shrink-0">
                    <span className="text-xs font-semibold text-accent">
                      {(member.user_full_name ?? member.user_email ?? "?")
                        .charAt(0)
                        .toUpperCase()}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-text truncate">
                      {member.user_full_name ?? member.user_email}
                    </p>
                    {member.user_full_name && (
                      <p className="text-xs text-text-muted truncate">{member.user_email}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <RoleBadge role={member.role} />
                    {member.status === "inactive" && (
                      <span className="text-xs text-text-muted">(Pasif)</span>
                    )}
                  </div>
                  {canManageMembers && member.user_id !== user?.id && member.role !== "owner" && (
                    <button className="text-text-muted hover:text-danger transition-colors p-1 ml-1">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                          d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  )}
                </div>
              ))
            )}
          </>
        )}

        {tab === "invitations" && (
          <>
            {isLoading ? (
              Array.from({ length: 2 }).map((_, i) => <SkeletonRow key={i} />)
            ) : invitations.length === 0 ? (
              <div className="px-6 py-12 text-center">
                <p className="text-sm text-text-muted">Bekleyen davet yok.</p>
              </div>
            ) : (
              invitations.map((inv) => {
                const isExpired = !inv.is_pending && !inv.accepted_at && !inv.revoked_at;

                return (
                  <div
                    key={inv.id}
                    className="flex items-center gap-4 px-6 py-4 border-b border-border last:border-0"
                  >
                    <div className="w-9 h-9 bg-surface-2 rounded-full flex items-center justify-center flex-shrink-0">
                      <svg className="w-4 h-4 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                          d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                      </svg>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-text truncate">{inv.email}</p>
                      <p className="text-xs text-text-muted">
                        {inv.accepted_at
                          ? `Kabul edildi: ${new Date(inv.accepted_at).toLocaleDateString("tr-TR")}`
                          : inv.revoked_at
                          ? `İptal edildi: ${new Date(inv.revoked_at).toLocaleDateString("tr-TR")}`
                          : isExpired
                          ? "Süresi doldu"
                          : `Son: ${new Date(inv.expires_at).toLocaleDateString("tr-TR")}`}
                      </p>
                    </div>
                    <RoleBadge role={inv.role} />
                    {canManageMembers && inv.is_pending && (
                      <div className="flex items-center gap-1.5 ml-1">
                        <button
                          onClick={() => handleResend(inv.id)}
                          className="text-xs text-text-muted hover:text-accent transition-colors px-2 py-1 rounded hover:bg-surface-2"
                        >
                          Tekrar Gönder
                        </button>
                        <button
                          onClick={() => handleRevoke(inv.id)}
                          className="text-xs text-text-muted hover:text-danger transition-colors px-2 py-1 rounded hover:bg-surface-2"
                        >
                          İptal
                        </button>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </>
        )}
      </div>

      {activeAgency && accessToken && (
        <InviteModal
          isOpen={showInviteModal}
          onClose={() => setShowInviteModal(false)}
          agencyId={activeAgency.id}
          accessToken={accessToken}
          onSuccess={loadData}
        />
      )}
    </div>
  );
}

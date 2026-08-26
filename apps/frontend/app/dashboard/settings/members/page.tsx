"use client";

import { useState, useEffect, useCallback } from "react";
import {
  agencyApi,
  invitationApi,
  partnershipInvitationApi,
  type AgencyMemberRead,
  type InvitationRead,
  type PartnershipInvitationRead,
} from "@/lib/api-client";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { Button } from "@/components/ui/button";
import { RoleBadge } from "@/components/team/role-badge";
import { InviteModal } from "@/components/team/invite-modal";
import { useLocale } from "@/context/locale-context";
import { Input } from "@/components/ui/input";
import { Handshake, Mail } from "lucide-react";

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
  const { intlLocale, t } = useLocale();
  const { user, accessToken } = useAuth();
  const { activeAgency, isLoading: workspaceLoading, isInitialized: workspaceReady } = useWorkspace();

  const [members, setMembers] = useState<AgencyMemberRead[]>([]);
  const [invitations, setInvitations] = useState<InvitationRead[]>([]);
  const [partnerInvitations, setPartnerInvitations] = useState<PartnershipInvitationRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [tab, setTab] = useState<"members" | "invitations" | "partners">("members");
  const [partnerEmail, setPartnerEmail] = useState("");
  const [partnerMessage, setPartnerMessage] = useState("");
  const [partnerError, setPartnerError] = useState<string | null>(null);
  const [partnerSubmitting, setPartnerSubmitting] = useState(false);
  const canManageMembers =
    activeAgency?.member_role === "owner" || activeAgency?.member_role === "admin";

  const loadData = useCallback(async () => {
    if (!activeAgency || !accessToken) return;

    setIsLoading(true);
    try {
      const [mems, invs, partnerInvites] = await Promise.all([
        agencyApi.listMembers(activeAgency.id, accessToken),
        invitationApi.listAgencyInvitations(activeAgency.id, accessToken),
        canManageMembers
          ? partnershipInvitationApi.listForAgency(activeAgency.id, accessToken)
          : Promise.resolve([]),
      ]);
      setMembers(mems);
      setInvitations(invs);
      setPartnerInvitations(partnerInvites);
    } finally {
      setIsLoading(false);
    }
  }, [activeAgency, accessToken, canManageMembers]);

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

  const pendingCount = invitations.filter((i) => i.is_pending).length;

  const handlePartnerInvite = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!activeAgency || !accessToken) return;
    setPartnerError(null);
    setPartnerSubmitting(true);
    try {
      await partnershipInvitationApi.createFromAgency(
        { email: partnerEmail.trim(), message: partnerMessage.trim() || null },
        activeAgency.id,
        accessToken
      );
      setPartnerEmail("");
      setPartnerMessage("");
      await loadData();
    } catch (err) {
      setPartnerError(err instanceof Error ? err.message : t("settings.members.partner.empty"));
    } finally {
      setPartnerSubmitting(false);
    }
  };

  if (!isLoading && !activeAgency) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="w-14 h-14 bg-surface-2 rounded-2xl flex items-center justify-center mb-4">
          <span className="text-2xl">◓</span>
        </div>
        <p className="text-base font-medium text-text">{t("settings.members.noAgencyTitle")}</p>
        <p className="text-sm text-text-muted mt-1 mb-4">{t("settings.members.noAgencyDescription")}</p>
        <a href="/onboarding/create-agency" className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors">
          {t("settings.members.createAgency")}
        </a>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6 flex justify-end">
        {canManageMembers && tab !== "partners" && (
          <Button onClick={() => setShowInviteModal(true)}>
            {t("settings.members.invite")}
          </Button>
        )}
      </div>

      <div className="flex gap-1 p-1 bg-surface-2 rounded-xl mb-6 w-fit">
        {(["members", "invitations", "partners"] as const).map((tabKey) => (
          <button
            key={tabKey}
            onClick={() => setTab(tabKey)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${
              tab === tabKey
                ? "bg-surface shadow-sm text-text"
                : "text-text-muted hover:text-text"
            }`}
          >
            {t(
              tabKey === "members"
                ? "settings.members.tab.members"
                : tabKey === "invitations"
                  ? "settings.members.tab.invitations"
                  : "settings.members.tab.partners"
            )}
            {tabKey === "invitations" && pendingCount > 0 && (
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
                <p className="text-sm text-text-muted">{t("settings.members.empty")}</p>
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
                      <span className="text-xs text-text-muted">{t("settings.members.inactive")}</span>
                    )}
                  </div>
                  {canManageMembers && member.user_id !== user?.id && member.role !== "owner" && (
                    <button
                      aria-label={t("settings.members.removeMember")}
                      className="text-text-muted hover:text-danger transition-colors p-1 ml-1"
                    >
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
                <p className="text-sm text-text-muted">{t("settings.members.noInvitations")}</p>
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
                          ? t("settings.members.invitation.accepted", {
                              date: new Date(inv.accepted_at).toLocaleDateString(intlLocale),
                            })
                          : inv.revoked_at
                            ? t("settings.members.invitation.revoked", {
                                date: new Date(inv.revoked_at).toLocaleDateString(intlLocale),
                              })
                            : isExpired
                              ? t("settings.members.invitation.expired")
                              : t("settings.members.invitation.expires", {
                                  date: new Date(inv.expires_at).toLocaleDateString(intlLocale),
                                })}
                      </p>
                    </div>
                    <RoleBadge role={inv.role} />
                    {canManageMembers && inv.is_pending && (
                      <div className="flex items-center gap-1.5 ml-1">
                        <button
                          onClick={() => handleResend(inv.id)}
                          className="text-xs text-text-muted hover:text-accent transition-colors px-2 py-1 rounded hover:bg-surface-2"
                        >
                          {t("settings.members.resend")}
                        </button>
                        <button
                          onClick={() => handleRevoke(inv.id)}
                          className="text-xs text-text-muted hover:text-danger transition-colors px-2 py-1 rounded hover:bg-surface-2"
                        >
                          {t("settings.members.cancel")}
                        </button>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </>
        )}

        {tab === "partners" && (
          <div className="space-y-0">
            {canManageMembers && (
              <form onSubmit={handlePartnerInvite} className="space-y-4 border-b border-border p-5">
                <div className="flex items-start gap-3">
                  <span className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-accent/10 text-accent">
                    <Handshake className="h-5 w-5" aria-hidden="true" />
                  </span>
                  <div>
                    <h2 className="text-sm font-semibold text-text">{t("settings.members.partner.title")}</h2>
                    <p className="mt-1 max-w-2xl text-xs leading-relaxed text-text-muted">
                      {t("settings.members.partner.description")}
                    </p>
                  </div>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Input
                    label={t("settings.members.partner.email")}
                    type="email"
                    required
                    value={partnerEmail}
                    onChange={(event) => setPartnerEmail(event.target.value)}
                  />
                  <Input
                    label={t("settings.members.partner.message")}
                    value={partnerMessage}
                    maxLength={500}
                    onChange={(event) => setPartnerMessage(event.target.value)}
                  />
                </div>
                {partnerError && <p className="text-xs text-danger">{partnerError}</p>}
                <Button type="submit" disabled={partnerSubmitting}>
                  <Mail className="h-4 w-4" aria-hidden="true" />
                  {t(partnerSubmitting ? "settings.members.partner.sending" : "settings.members.partner.send")}
                </Button>
              </form>
            )}
            {partnerInvitations.length === 0 ? (
              <p className="px-5 py-10 text-center text-sm text-text-muted">
                {t("settings.members.partner.empty")}
              </p>
            ) : (
              partnerInvitations.map((invitation) => (
                <div key={invitation.id} className="flex items-center gap-4 border-b border-border px-5 py-4 last:border-0">
                  <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-surface-2">
                    <Handshake className="h-4 w-4 text-text-muted" aria-hidden="true" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-text">{invitation.email}</p>
                    <p className="text-xs text-text-muted">
                      {invitation.accepted_at
                        ? t("settings.members.partner.accepted")
                        : invitation.revoked_at
                          ? t("settings.members.partner.revoked")
                          : t("settings.members.partner.pending")}
                    </p>
                  </div>
                  {canManageMembers && invitation.is_pending && (
                    <button
                      type="button"
                      onClick={async () => {
                        if (!accessToken) return;
                        await partnershipInvitationApi.revoke(invitation.id, accessToken);
                        await loadData();
                      }}
                      className="min-h-9 rounded-lg px-3 text-xs font-medium text-text-muted transition-colors hover:bg-surface-2 hover:text-danger"
                    >
                      {t("settings.members.cancel")}
                    </button>
                  )}
                </div>
              ))
            )}
          </div>
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

"use client";

import { useCallback, useEffect, useState } from "react";
import { useLocale } from "@/context/locale-context";
import {
  ApiError,
  platformApi,
  type PlatformAgencyMemberRead,
  type PlatformBrandMemberRead,
  type PlatformInvitationRead,
} from "@/lib/api-client";
import { platformAuthStorage } from "@/lib/platform-auth";
import type { TranslationKey } from "@/messages";
import { ConfirmActionModal } from "./ConfirmActionModal";

type RecoveryTarget =
  | { type: "agency"; id: string; agencyName: string }
  | { type: "brand"; id: string; agencyName?: string; brandName: string };

interface MembershipRecoveryPanelProps {
  target: RecoveryTarget;
  onMemberAdded: (member: PlatformAgencyMemberRead | PlatformBrandMemberRead) => void;
}

const agencyRoles = ["owner", "admin", "brand_manager", "designer", "developer", "social_media_manager", "viewer"];
const brandRoles = ["brand_owner", "brand_manager", "brand_viewer", "external_approver"];
const roleKeys: Record<string, TranslationKey> = {
  owner: "platform.role.owner",
  admin: "platform.role.admin",
  brand_manager: "platform.role.brandManager",
  designer: "platform.role.designer",
  developer: "platform.role.developer",
  social_media_manager: "platform.role.socialMediaManager",
  viewer: "platform.role.viewer",
  brand_owner: "platform.role.brandOwner",
  brand_viewer: "platform.role.brandViewer",
  external_approver: "platform.role.externalApprover",
};
const fieldClass = "w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus:border-accent";

export function MembershipRecoveryPanel({ target, onMemberAdded }: MembershipRecoveryPanelProps) {
  const { locale, t } = useLocale();
  const [mode, setMode] = useState<"invite" | "attach">("invite");
  const [email, setEmail] = useState("");
  const roles = target.type === "agency" ? agencyRoles : brandRoles;
  const [role, setRole] = useState(roles[0]);
  const [invitations, setInvitations] = useState<PlatformInvitationRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [confirm, setConfirm] = useState<{ kind: "attach" | "revoke"; invitation?: PlatformInvitationRead } | null>(null);
  const targetId = target.id;
  const targetType = target.type;

  const loadInvitations = useCallback(async () => {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setLoading(true);
    try {
      const items = targetType === "agency"
        ? await platformApi.listAgencyInvitations(targetId, token)
        : await platformApi.listBrandInvitations(targetId, token);
      setInvitations(items);
    } catch (err) {
      setMessage({ kind: "err", text: err instanceof ApiError ? err.message : t("platform.provision.required") });
    } finally {
      setLoading(false);
    }
  }, [t, targetId, targetType]);

  useEffect(() => { void loadInvitations(); }, [loadInvitations]);

  async function submit() {
    const token = platformAuthStorage.getToken();
    if (!token || !email.includes("@")) {
      setMessage({ kind: "err", text: t("platform.provision.required") });
      return;
    }
    setSaving(true); setMessage(null);
    try {
      if (mode === "invite") {
        const invitation = target.type === "agency"
          ? await platformApi.inviteAgencyMemberByPlatform(target.id, { email, role, locale }, token)
          : await platformApi.inviteBrandMemberByPlatform(target.id, { email, role, locale }, token);
        setInvitations((items) => [invitation, ...items]);
        setMessage({ kind: "ok", text: t("platform.recovery.invited") });
      } else {
        const member = target.type === "agency"
          ? await platformApi.attachAgencyMemberByPlatform(target.id, { email, role, confirm_existing_user: true }, token)
          : await platformApi.attachBrandMemberByPlatform(target.id, { email, role, confirm_existing_user: true }, token);
        onMemberAdded(member);
        setMessage({ kind: "ok", text: t("platform.recovery.attached") });
      }
      setEmail(""); setConfirm(null);
    } catch (err) {
      setMessage({ kind: "err", text: err instanceof ApiError ? err.message : t("platform.provision.required") });
    } finally {
      setSaving(false);
    }
  }

  async function resend(invitation: PlatformInvitationRead) {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setSaving(true); setMessage(null);
    try {
      const updated = target.type === "agency"
        ? await platformApi.resendAgencyInvitation(target.id, invitation.id, token)
        : await platformApi.resendBrandInvitation(target.id, invitation.id, token);
      setInvitations((items) => items.map((item) => item.id === updated.id ? updated : item));
      setMessage({ kind: "ok", text: t("platform.recovery.resent") });
    } catch (err) {
      setMessage({ kind: "err", text: err instanceof ApiError ? err.message : t("platform.provision.required") });
    } finally { setSaving(false); }
  }

  async function revoke() {
    const invitation = confirm?.invitation;
    const token = platformAuthStorage.getToken();
    if (!token || !invitation) return;
    setSaving(true); setMessage(null);
    try {
      if (target.type === "agency") await platformApi.revokeAgencyInvitation(target.id, invitation.id, token);
      else await platformApi.revokeBrandInvitation(target.id, invitation.id, token);
      setInvitations((items) => items.map((item) => item.id === invitation.id ? { ...item, state: "revoked" } : item));
      setMessage({ kind: "ok", text: t("platform.recovery.revoked") });
      setConfirm(null);
    } catch (err) {
      setMessage({ kind: "err", text: err instanceof ApiError ? err.message : t("platform.provision.required") });
    } finally { setSaving(false); }
  }

  const targetDetails = target.type === "agency"
    ? { agency: target.agencyName }
    : { agency: target.agencyName, brand: target.brandName };

  return (
    <section className="rounded-xl border border-border bg-surface-2 p-4" data-testid="membership-recovery">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-text">{t("platform.recovery.title")}</h3>
        <p className="mt-1 text-xs leading-5 text-text-muted">{t("platform.confirm.warning")}</p>
      </div>

      {message && <div className={`mb-3 rounded-lg px-3 py-2 text-xs ${message.kind === "ok" ? "status-success" : "status-danger"}`}>{message.text}</div>}

      <div className="mb-3 grid grid-cols-2 rounded-lg border border-border bg-surface p-1">
        <button className={`rounded-md px-2 py-2 text-xs font-medium ${mode === "invite" ? "bg-accent text-white" : "text-text-muted"}`} onClick={() => { setMode("invite"); setRole(roles[0]); }} type="button">{t("platform.recovery.invite")}</button>
        <button className={`rounded-md px-2 py-2 text-xs font-medium ${mode === "attach" ? "bg-warning text-background" : "text-text-muted"}`} onClick={() => { setMode("attach"); setRole(roles[0]); }} type="button">{t("platform.recovery.attach")}</button>
      </div>

      <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_160px_auto]">
        <label className="text-[11px] font-medium text-text-muted">{t("platform.recovery.email")}<input className={`${fieldClass} mt-1`} onChange={(event) => setEmail(event.target.value)} placeholder="name@company.com" type="email" value={email} /></label>
        <label className="text-[11px] font-medium text-text-muted">{t("platform.provision.role")}<select className={`${fieldClass} mt-1`} onChange={(event) => setRole(event.target.value)} value={role}>{roles.map((item) => <option key={item} value={item}>{t(roleKeys[item])}</option>)}</select></label>
        <button
          className="self-end rounded-lg bg-accent px-3 py-2 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
          disabled={saving}
          onClick={() => mode === "attach" ? setConfirm({ kind: "attach" }) : void submit()}
          type="button"
        >
          {mode === "attach" ? t("platform.recovery.attachUser") : t("platform.recovery.sendInvite")}
        </button>
      </div>

      <div className="mt-5 border-t border-border pt-4">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-muted">{t("platform.recovery.pending")}</p>
        {loading ? <div className="h-12 animate-pulse rounded-lg bg-surface" /> : invitations.length === 0 ? <p className="py-3 text-center text-xs text-text-muted">{t("platform.recovery.noInvites")}</p> : (
          <div className="space-y-2">
            {invitations.map((invitation) => <div className="rounded-lg border border-border bg-surface px-3 py-2.5" key={invitation.id}>
              <div className="flex flex-wrap items-start justify-between gap-2"><div className="min-w-0"><p className="truncate text-xs font-medium text-text">{invitation.email}</p><p className="mt-0.5 text-[11px] text-text-muted">{invitation.role} · {invitation.state}</p></div>{invitation.state === "pending" && <div className="flex gap-1"><button className="rounded-md px-2 py-1 text-[11px] font-medium text-accent hover:bg-accent/10 disabled:opacity-50" disabled={saving} onClick={() => void resend(invitation)} type="button">{t("platform.recovery.resend")}</button><button className="rounded-md px-2 py-1 text-[11px] font-medium text-danger hover:bg-danger/10 disabled:opacity-50" disabled={saving} onClick={() => setConfirm({ kind: "revoke", invitation })} type="button">{t("platform.recovery.revoke")}</button></div>}</div>
            </div>)}
          </div>
        )}
      </div>

      <ConfirmActionModal
        destructive={confirm?.kind === "revoke"}
        details={{ action: confirm?.kind === "revoke" ? t("platform.confirm.revoke") : t("platform.confirm.attach"), ...targetDetails, user: confirm?.invitation?.email ?? email, role: confirm?.invitation?.role ?? role }}
        loading={saving}
        onClose={() => setConfirm(null)}
        onConfirm={() => confirm?.kind === "revoke" ? void revoke() : void submit()}
        open={Boolean(confirm)}
      />
    </section>
  );
}

"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Handshake, LockKeyhole, ShieldCheck } from "lucide-react";
import { AuthCard } from "@/components/auth/auth-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import {
  ApiError,
  partnershipInvitationApi,
  type PartnershipInvitationPreview,
} from "@/lib/api-client";
import { useLocale } from "@/context/locale-context";

export default function PartnershipInvitationPage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const { t } = useLocale();
  const { user, accessToken } = useAuth();
  const { agencies, brands, refreshWorkspaces } = useWorkspace();
  const token = params.token;
  const [preview, setPreview] = useState<PartnershipInvitationPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [createNew, setCreateNew] = useState(false);
  const [newWorkspaceName, setNewWorkspaceName] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    partnershipInvitationApi
      .preview(token)
      .then((result) => {
        setPreview(result);
        if (result.state !== "pending") setError(t("auth.partner.invalid"));
      })
      .catch(() => setError(t("auth.partner.invalid")))
      .finally(() => setLoading(false));
  }, [t, token]);

  const eligibleWorkspaces = useMemo(() => {
    if (!preview) return [];
    return preview.required_workspace_type === "brand"
      ? brands.filter((brand) => brand.member_role === "brand_owner" && brand.agency_id === null)
      : agencies.filter((agency) => agency.member_role === "owner");
  }, [agencies, brands, preview]);

  useEffect(() => {
    if (!selectedId && eligibleWorkspaces.length > 0) {
      setSelectedId(eligibleWorkspaces[0].id);
    }
    if (eligibleWorkspaces.length === 0) setCreateNew(true);
  }, [eligibleWorkspaces, selectedId]);

  async function handleAccept() {
    if (!accessToken || !preview) return;
    setError(null);
    setSubmitting(true);
    try {
      const result = await partnershipInvitationApi.accept(
        token,
        createNew
          ? { new_workspace_name: newWorkspaceName.trim() }
          : { target_workspace_id: selectedId },
        accessToken
      );
      await refreshWorkspaces();
      router.replace(result.redirect_to);
    } catch (caught) {
      setError(
        caught instanceof ApiError || caught instanceof Error
          ? caught.message
          : t("auth.partner.invalid")
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <AuthCard wide>
        <div className="py-12 text-center text-sm text-text-muted">{t("auth.partner.loading")}</div>
      </AuthCard>
    );
  }

  if (!preview || error && preview?.state !== "pending") {
    return (
      <AuthCard wide>
        <div className="py-10 text-center">
          <LockKeyhole className="mx-auto mb-4 h-10 w-10 text-danger" aria-hidden="true" />
          <h1 className="text-xl font-semibold text-text">{t("auth.partner.title")}</h1>
          <p className="mt-2 text-sm text-text-muted">{error ?? t("auth.partner.invalid")}</p>
        </div>
      </AuthCard>
    );
  }

  const returnPath = `/partner-invite/${encodeURIComponent(token)}`;
  const description = t(
    preview.direction === "agency_invites_brand"
      ? "auth.partner.agencyInvitesBrand"
      : "auth.partner.brandInvitesAgency",
    { source: preview.source_name }
  );

  return (
    <AuthCard wide>
      <div className="space-y-6">
        <div className="flex items-start gap-4">
          <span className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-2xl bg-accent/10 text-accent">
            <Handshake className="h-6 w-6" aria-hidden="true" />
          </span>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-accent">PostPiloter</p>
            <h1 className="mt-1 text-2xl font-bold text-text">{t("auth.partner.title")}</h1>
            <p className="mt-2 text-sm leading-relaxed text-text-muted">{description}</p>
          </div>
        </div>

        <div className="flex items-start gap-3 rounded-xl border border-success/20 bg-success/5 p-4">
          <ShieldCheck className="mt-0.5 h-5 w-5 flex-shrink-0 text-success" aria-hidden="true" />
          <p className="text-xs leading-relaxed text-text-muted">{t("auth.partner.securityNote")}</p>
        </div>

        {!user || !accessToken ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <Link
              href={`/auth/login?redirect=${encodeURIComponent(returnPath)}`}
              className="flex min-h-11 items-center justify-center rounded-xl bg-accent px-4 text-sm font-semibold text-white transition-colors hover:bg-accent-hover"
            >
              {t("auth.partner.login")}
            </Link>
            <Link
              href={`/auth/register?workspace_type=${preview.required_workspace_type}&redirect=${encodeURIComponent(returnPath)}`}
              className="flex min-h-11 items-center justify-center rounded-xl border border-border bg-surface-2 px-4 text-center text-sm font-semibold text-text transition-colors hover:border-accent/40"
            >
              {t("auth.partner.register")}
            </Link>
          </div>
        ) : user.email.toLowerCase() !== preview.email.toLowerCase() ? (
          <div className="rounded-xl border border-danger/20 bg-danger/10 p-4 text-sm text-danger">
            {t("auth.partner.wrongEmail", { email: preview.email })}
          </div>
        ) : (
          <div className="space-y-4">
            {eligibleWorkspaces.length > 0 && !createNew && (
              <label className="block text-xs font-medium text-text-muted">
                {t("auth.partner.selectWorkspace")}
                <select
                  value={selectedId}
                  onChange={(event) => setSelectedId(event.target.value)}
                  className="mt-1.5 h-11 w-full rounded-lg border border-border bg-surface-2 px-3 text-sm text-text focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
                >
                  {eligibleWorkspaces.map((workspace) => (
                    <option key={workspace.id} value={workspace.id}>{workspace.name}</option>
                  ))}
                </select>
              </label>
            )}

            {createNew && (
              <>
                {eligibleWorkspaces.length === 0 && (
                  <p className="text-xs text-text-muted">{t("auth.partner.noWorkspace")}</p>
                )}
                <Input
                  label={t("auth.partner.newWorkspaceName")}
                  value={newWorkspaceName}
                  minLength={2}
                  maxLength={120}
                  required
                  onChange={(event) => setNewWorkspaceName(event.target.value)}
                />
              </>
            )}

            {eligibleWorkspaces.length > 0 && (
              <button
                type="button"
                onClick={() => setCreateNew((previous) => !previous)}
                className="text-xs font-medium text-accent hover:text-accent-hover"
              >
                {createNew ? t("auth.partner.selectWorkspace") : t("auth.partner.createNew")}
              </button>
            )}

            {error && <p className="rounded-lg bg-danger/10 px-3 py-2 text-xs text-danger">{error}</p>}
            <Button
              className="w-full"
              disabled={submitting || (createNew ? newWorkspaceName.trim().length < 2 : !selectedId)}
              onClick={handleAccept}
            >
              {submitting ? t("auth.partner.accepting") : t("auth.partner.accept")}
            </Button>
          </div>
        )}
      </div>
    </AuthCard>
  );
}

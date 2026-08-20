"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { invitationApi, type InvitationPreview } from "@/lib/api-client";
import { useAuth } from "@/hooks/useAuth";
import { useLocale } from "@/context/locale-context";
import { LanguageSelector } from "@/components/i18n/language-selector";
import type { Locale } from "@/lib/i18n/config";

const ROLE_LABEL: Record<string, Record<Locale, string>> = {
  owner: { en: "Owner", tr: "Sahip" },
  admin: { en: "Administrator", tr: "Yönetici" },
  brand_manager: { en: "Brand manager", tr: "Marka Yöneticisi" },
  designer: { en: "Designer", tr: "Tasarımcı" },
  developer: { en: "Developer", tr: "Geliştirici" },
  social_media_manager: { en: "Social media manager", tr: "Sosyal Medya Yöneticisi" },
  viewer: { en: "Viewer", tr: "İzleyici" },
  brand_owner: { en: "Brand owner", tr: "Marka Sahibi" },
  brand_viewer: { en: "Brand viewer", tr: "Marka İzleyicisi" },
  external_approver: { en: "External approver", tr: "Harici Onaylayıcı" },
};

function RoleBadge({ role, locale }: { role: string; locale: Locale }) {
  return (
    <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
      {ROLE_LABEL[role]?.[locale] ?? role}
    </span>
  );
}

function formatExpiry(dateStr: string, locale: Locale, t: ReturnType<typeof useLocale>["t"]): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays <= 0) return t("auth.invite.expiresToday");
  if (diffDays === 1) return t("auth.invite.expiresTomorrow");
  return t("auth.invite.expiresInDays", { count: diffDays });
}

function AgencyInitials({ name }: { name: string }) {
  const initials = name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
  return (
    <div className="w-16 h-16 rounded-2xl bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center">
      <span className="text-2xl font-bold text-indigo-400">{initials}</span>
    </div>
  );
}

type PageState = "loading" | "pending" | "not-pending" | "accepted" | "rejected" | "error";

export default function InviteTokenPage() {
  const { locale, t } = useLocale();
  const { token } = useParams<{ token: string }>();
  const { user, accessToken, isInitialized, isLoading: authLoading } = useAuth();
  const router = useRouter();

  const [preview, setPreview] = useState<InvitationPreview | null>(null);
  const [pageState, setPageState] = useState<PageState>("loading");
  const [actionLoading, setActionLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    if (!token) return;
    invitationApi
      .getPreview(token)
      .then((p) => {
        setPreview(p);
        setPageState(p.is_pending ? "pending" : "not-pending");
      })
      .catch(() => {
        setPageState("error");
      });
  }, [token]);

  const handleAccept = async () => {
    if (!isInitialized || authLoading) return;
    if (!user || !accessToken) {
      router.push(`/auth/login?redirect=/invite/${token}`);
      return;
    }
    setActionLoading(true);
    setErrorMsg("");
    try {
      await invitationApi.accept(token, accessToken);
      setPageState("accepted");
      setTimeout(() => router.push("/dashboard"), 2500);
    } catch (err: unknown) {
      const e = err as { message?: string };
      setErrorMsg(e?.message ?? t("auth.error.generic"));
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!preview) return;
    if (!user || !accessToken) {
      setPageState("rejected");
      return;
    }
    setActionLoading(true);
    setErrorMsg("");
    try {
      await invitationApi.reject(preview.id, accessToken);
      setPageState("rejected");
    } catch (err: unknown) {
      const e = err as { message?: string };
      setErrorMsg(e?.message ?? t("auth.error.generic"));
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center px-4"
      style={{ background: "#0A0A0F" }}
    >
      <div
        className="w-full max-w-[480px] rounded-2xl border p-8 shadow-2xl"
        style={{ background: "#111118", borderColor: "rgba(99,102,241,0.2)" }}
      >
        <div className="mb-5 flex justify-end">
          <LanguageSelector compact />
        </div>
        {/* Loading */}
        {pageState === "loading" && (
          <div className="flex flex-col items-center gap-4 py-8">
            <svg
              className="w-8 h-8 animate-spin text-indigo-500"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v8z"
              />
            </svg>
            <p className="text-sm text-gray-400">{t("auth.invite.loading")}</p>
          </div>
        )}

        {/* Error */}
        {pageState === "error" && (
          <div className="flex flex-col items-center gap-4 py-8 text-center">
            <div className="w-14 h-14 rounded-full bg-red-500/10 border border-red-500/20 flex items-center justify-center">
              <svg
                className="w-7 h-7 text-red-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-white">{t("auth.invite.invalidTitle")}</h2>
            <p className="text-sm text-gray-400">
              {t("auth.invite.notFound")}
            </p>
            <button
              onClick={() => router.push("/")}
              className="mt-2 px-4 py-2 rounded-lg text-sm font-medium text-indigo-400 hover:text-indigo-300 border border-indigo-500/30 hover:border-indigo-400/50 transition-colors"
            >
              {t("auth.invite.home")}
            </button>
          </div>
        )}

        {/* Not pending */}
        {pageState === "not-pending" && preview && (
          <div className="flex flex-col items-center gap-4 py-8 text-center">
            <div className="w-14 h-14 rounded-full bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
              <svg
                className="w-7 h-7 text-amber-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-white">{t("auth.invite.noLongerValidTitle")}</h2>
            <p className="text-sm text-gray-400">
              {t("auth.invite.noLongerValidBody")}
            </p>
            <button
              onClick={() => router.push("/dashboard")}
              className="mt-2 px-4 py-2 rounded-lg text-sm font-medium bg-indigo-600 hover:bg-indigo-500 text-white transition-colors"
            >
              {t("auth.invite.goDashboard")}
            </button>
          </div>
        )}

        {/* Accepted */}
        {pageState === "accepted" && (
          <div className="flex flex-col items-center gap-4 py-8 text-center">
            <div className="w-14 h-14 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
              <svg
                className="w-7 h-7 text-emerald-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-white">{t("auth.invite.acceptedTitle")}</h2>
            <p className="text-sm text-gray-400">{t("auth.invite.redirecting")}</p>
          </div>
        )}

        {/* Rejected */}
        {pageState === "rejected" && (
          <div className="flex flex-col items-center gap-4 py-8 text-center">
            <div className="w-14 h-14 rounded-full bg-zinc-500/10 border border-zinc-500/20 flex items-center justify-center">
              <svg
                className="w-7 h-7 text-zinc-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-white">{t("auth.invite.rejectedTitle")}</h2>
            <p className="text-sm text-gray-400">{t("auth.invite.rejectedBody")}</p>
            <button
              onClick={() => router.push("/")}
              className="mt-2 px-4 py-2 rounded-lg text-sm font-medium text-gray-400 hover:text-gray-300 border border-gray-500/30 transition-colors"
            >
              {t("auth.invite.home")}
            </button>
          </div>
        )}

        {/* Pending — main invite card */}
        {pageState === "pending" && preview && (
          <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col items-center text-center gap-3">
              <AgencyInitials name={preview.agency_name} />
              <div>
                <h1 className="text-xl font-bold text-white">{preview.agency_name}</h1>
                {preview.brand_name && (
                  <p className="text-sm text-gray-400 mt-0.5">→ {preview.brand_name}</p>
                )}
              </div>
            </div>

            {/* Invite info */}
            <div
              className="rounded-xl p-5 space-y-3"
              style={{ background: "rgba(99,102,241,0.05)", border: "1px solid rgba(99,102,241,0.15)" }}
            >
              <p className="text-sm text-gray-300 text-center">
                {t("auth.invite.invitedToTeam", { agency: preview.agency_name })}
              </p>
              <div className="flex items-center justify-center gap-2">
                <span className="text-xs text-gray-500">{t("auth.invite.role")}</span>
                <RoleBadge role={preview.role} locale={locale} />
              </div>
              <p className="text-xs text-gray-500 text-center">
                {formatExpiry(preview.expires_at, locale, t)}
              </p>
            </div>

            {/* Error */}
            {errorMsg && (
              <div className="rounded-lg px-4 py-3 bg-red-500/10 border border-red-500/20 text-xs text-red-400">
                {errorMsg}
              </div>
            )}

            {/* Login notice */}
            {!user && isInitialized && !authLoading && (
              <div className="rounded-lg px-4 py-3 bg-blue-500/10 border border-blue-500/20 text-xs text-blue-300 text-center">
                {t("auth.invite.loginRequired")}
              </div>
            )}

            {/* Actions */}
            <div className="flex flex-col gap-3">
              <button
                onClick={handleAccept}
                disabled={actionLoading || authLoading}
                className="w-full py-3 rounded-xl text-sm font-semibold text-white transition-all disabled:opacity-60 disabled:cursor-not-allowed"
                style={{ background: "#6366F1" }}
                onMouseEnter={(e) => {
                  if (!actionLoading) (e.currentTarget as HTMLButtonElement).style.background = "#5457e5";
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.background = "#6366F1";
                }}
              >
                {actionLoading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                    </svg>
                    {t("auth.invite.processing")}
                  </span>
                ) : user ? (
                  t("auth.invite.accept")
                ) : (
                  t("auth.invite.loginAccept")
                )}
              </button>
              <button
                onClick={handleReject}
                disabled={actionLoading}
                className="w-full py-3 rounded-xl text-sm font-medium text-gray-400 hover:text-gray-300 border transition-colors disabled:opacity-60"
                style={{ borderColor: "rgba(255,255,255,0.1)" }}
              >
                {t("auth.invite.decline")}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

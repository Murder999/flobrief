"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { invitationApi, type InvitationPreview } from "@/lib/api-client";
import { useAuth } from "@/hooks/useAuth";

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
    <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
      {ROLE_LABEL[role] ?? role}
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
  return `${diffDays} gün sonra sona eriyor`;
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
      setErrorMsg(e?.message ?? "Bir hata oluştu.");
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
      setErrorMsg(e?.message ?? "Bir hata oluştu.");
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
            <p className="text-sm text-gray-400">Davet yükleniyor…</p>
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
            <h2 className="text-lg font-semibold text-white">Davet bulunamadı</h2>
            <p className="text-sm text-gray-400">
              Bu davet linki geçersiz veya süresi dolmuş olabilir.
            </p>
            <button
              onClick={() => router.push("/")}
              className="mt-2 px-4 py-2 rounded-lg text-sm font-medium text-indigo-400 hover:text-indigo-300 border border-indigo-500/30 hover:border-indigo-400/50 transition-colors"
            >
              Ana sayfaya dön
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
            <h2 className="text-lg font-semibold text-white">Bu davet artık geçerli değil</h2>
            <p className="text-sm text-gray-400">
              Bu davet kabul edilmiş, iptal edilmiş ya da süresi dolmuş olabilir.
            </p>
            <button
              onClick={() => router.push("/dashboard")}
              className="mt-2 px-4 py-2 rounded-lg text-sm font-medium bg-indigo-600 hover:bg-indigo-500 text-white transition-colors"
            >
              Dashboard&apos;a git
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
            <h2 className="text-lg font-semibold text-white">Davet kabul edildi!</h2>
            <p className="text-sm text-gray-400">Dashboard&apos;a yönlendiriliyorsunuz…</p>
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
            <h2 className="text-lg font-semibold text-white">Davet reddedildi</h2>
            <p className="text-sm text-gray-400">Bu daveti reddettiğiniz kaydedildi.</p>
            <button
              onClick={() => router.push("/")}
              className="mt-2 px-4 py-2 rounded-lg text-sm font-medium text-gray-400 hover:text-gray-300 border border-gray-500/30 transition-colors"
            >
              Ana sayfaya dön
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
                Sizi{" "}
                <span className="font-semibold text-white">{preview.agency_name}</span> ekibine
                katılmaya davet etti
              </p>
              <div className="flex items-center justify-center gap-2">
                <span className="text-xs text-gray-500">Rol:</span>
                <RoleBadge role={preview.role} />
              </div>
              <p className="text-xs text-gray-500 text-center">
                {formatExpiry(preview.expires_at)}
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
                Kabul etmek için giriş yapmanız gerekiyor.
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
                    İşleniyor…
                  </span>
                ) : user ? (
                  "Kabul Et"
                ) : (
                  "Giriş Yap ve Kabul Et"
                )}
              </button>
              <button
                onClick={handleReject}
                disabled={actionLoading}
                className="w-full py-3 rounded-xl text-sm font-medium text-gray-400 hover:text-gray-300 border transition-colors disabled:opacity-60"
                style={{ borderColor: "rgba(255,255,255,0.1)" }}
              >
                Reddet
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

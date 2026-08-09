"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { invitationApi, type InvitationPreview } from "@/lib/api-client";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { Button } from "@/components/ui/button";
import { RoleBadge } from "@/components/team/role-badge";

type PageState = "loading" | "preview" | "accepting" | "accepted" | "error";

function AcceptInviteContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { user, accessToken } = useAuth();
  const { refreshWorkspaces, switchAgency } = useWorkspace();

  const token = searchParams.get("token") ?? "";
  const [state, setState] = useState<PageState>("loading");
  const [preview, setPreview] = useState<InvitationPreview | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>("");

  useEffect(() => {
    if (!token) {
      setErrorMsg("Davet bağlantısı geçersiz.");
      setState("error");
      return;
    }

    invitationApi
      .getPreview(token)
      .then((data) => {
        setPreview(data);
        setState("preview");
      })
      .catch((err: unknown) => {
        setErrorMsg(err instanceof Error ? err.message : "Davet bulunamadı veya süresi dolmuş.");
        setState("error");
      });
  }, [token]);

  const handleAccept = async () => {
    if (!accessToken) {
      router.push(`/auth/login?redirect=/auth/accept-invite?token=${token}`);
      return;
    }

    setState("accepting");
    try {
      await invitationApi.accept(token, accessToken);
      await refreshWorkspaces();
      if (preview?.agency_id) {
        switchAgency(preview.agency_id);
      }
      setState("accepted");
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Davet kabul edilemedi.");
      setState("error");
    }
  };

  if (state === "loading") {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex items-center gap-3 text-text-muted">
          <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span className="text-sm">Davet yükleniyor…</span>
        </div>
      </div>
    );
  }

  if (state === "accepted") {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="text-center max-w-sm">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-success/20 rounded-2xl mb-4">
            <svg className="w-7 h-7 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h1 className="text-xl font-bold text-text mb-2">Daveti Kabul Ettiniz</h1>
          <p className="text-sm text-text-muted mb-6">
            {preview?.agency_name && `${preview.agency_name} ekibine hoş geldiniz.`}
          </p>
          <Button onClick={() => router.replace("/dashboard")} className="w-full">
            Dashboard&apos;a Git
          </Button>
        </div>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="text-center max-w-sm">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-danger/20 rounded-2xl mb-4">
            <svg className="w-7 h-7 text-danger" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
          <h1 className="text-xl font-bold text-text mb-2">Davet Geçersiz</h1>
          <p className="text-sm text-text-muted mb-6">{errorMsg}</p>
          <Button onClick={() => router.replace("/")} variant="secondary" className="w-full">
            Ana Sayfaya Dön
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 bg-accent/20 rounded-2xl mb-4">
            <span className="text-xl font-bold text-accent">F</span>
          </div>
          <h1 className="text-2xl font-bold text-text">Davet Aldınız</h1>
          <p className="mt-1 text-sm text-text-muted">
            Aşağıdaki daveti kabul ederek Flobrief&apos;e katılabilirsiniz.
          </p>
        </div>

        <div className="bg-surface border border-border rounded-2xl p-6 space-y-4">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 bg-accent/20 rounded-xl flex items-center justify-center flex-shrink-0">
              <span className="text-base font-bold text-accent uppercase">
                {preview?.agency_name?.charAt(0) ?? "?"}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-text">{preview?.agency_name}</p>
              {preview?.brand_name && (
                <p className="text-sm text-text-muted">{preview.brand_name}</p>
              )}
              <div className="mt-1">
                <RoleBadge role={preview?.role ?? ""} />
              </div>
            </div>
          </div>

          {preview?.message && (
            <div className="px-4 py-3 bg-surface-2 rounded-xl border border-border">
              <p className="text-xs text-text-muted mb-1">Mesaj</p>
              <p className="text-sm text-text">{preview.message}</p>
            </div>
          )}

          <div className="pt-2 flex flex-col gap-2">
            {!user ? (
              <>
                <p className="text-xs text-text-muted text-center mb-1">
                  Daveti kabul etmek için giriş yapmanız gerekiyor.
                </p>
                <Button
                  onClick={() =>
                    router.push(`/auth/login?redirect=/auth/accept-invite?token=${token}`)
                  }
                  className="w-full"
                >
                  Giriş Yap ve Kabul Et
                </Button>
                <Button
                  onClick={() =>
                    router.push(`/auth/register?redirect=/auth/accept-invite?token=${token}`)
                  }
                  variant="secondary"
                  className="w-full"
                >
                  Hesap Oluştur ve Kabul Et
                </Button>
              </>
            ) : (
              <>
                <p className="text-xs text-text-muted text-center mb-1">
                  <span className="font-medium text-text">{user.email}</span> hesabıyla kabul ediyorsunuz.
                </p>
                <Button
                  onClick={handleAccept}
                  disabled={state === "accepting"}
                  className="w-full"
                >
                  {state === "accepting" ? "Kabul Ediliyor…" : "Daveti Kabul Et"}
                </Button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AcceptInvitePage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-background flex items-center justify-center">
          <div className="flex items-center gap-3 text-text-muted">
            <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span className="text-sm">Yükleniyor…</span>
          </div>
        </div>
      }
    >
      <AcceptInviteContent />
    </Suspense>
  );
}

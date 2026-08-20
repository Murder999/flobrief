"use client";

import { Button } from "@/components/ui/button";
import { AuthCard } from "@/components/auth/auth-card";
import { authApi, ApiError } from "@/lib/api-client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { useLocale } from "@/context/locale-context";

type State = "loading" | "success" | "error" | "no-token";

function VerifyEmailContent() {
  const { t } = useLocale();
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [state, setState] = useState<State>(token ? "loading" : "no-token");
  const [errorMessage, setErrorMessage] = useState<string>("");

  useEffect(() => {
    if (!token) {
      setState("no-token");
      return;
    }

    let cancelled = false;
    authApi
      .verifyEmail(token)
      .then(() => {
        if (!cancelled) setState("success");
      })
      .catch((err) => {
        if (!cancelled) {
          setErrorMessage(
            err instanceof ApiError && err.status === 400
              ? t("auth.verify.expired")
              : t("auth.verify.generic")
          );
          setState("error");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [t, token]);

  if (state === "loading") {
    return (
      <div className="text-center">
        <div className="w-12 h-12 bg-surface-2 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg
            className="w-6 h-6 text-text-muted animate-spin"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>
        <h2 className="text-xl font-bold text-text mb-2">{t("auth.verify.loadingTitle")}</h2>
        <p className="text-sm text-text-muted">{t("auth.verify.loadingBody")}</p>
      </div>
    );
  }

  if (state === "success") {
    return (
      <div className="text-center">
        <div className="w-12 h-12 bg-success/10 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg className="w-6 h-6 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h2 className="text-xl font-bold text-text mb-2">{t("auth.verify.successTitle")}</h2>
        <p className="text-sm text-text-muted mb-6">
          {t("auth.verify.successBody")}
        </p>
        <Button className="w-full" onClick={() => router.push("/auth/login")}>
          {t("auth.actions.login")}
        </Button>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className="text-center">
        <div className="w-12 h-12 bg-danger/10 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg className="w-6 h-6 text-danger" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </div>
        <h2 className="text-xl font-bold text-text mb-2">{t("auth.verify.failedTitle")}</h2>
        <p className="text-sm text-text-muted mb-6">{errorMessage}</p>
        <Link href="/auth/login">
          <Button variant="secondary" className="w-full mb-3">{t("auth.backToLogin")}</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="text-center">
      <div className="w-12 h-12 bg-accent/10 rounded-full flex items-center justify-center mx-auto mb-4">
        <svg className="w-6 h-6 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
          />
        </svg>
      </div>
      <h2 className="text-xl font-bold text-text mb-2">{t("auth.verify.checkTitle")}</h2>
      <p className="text-sm text-text-muted mb-6">
        {t("auth.verify.checkBody")}
      </p>
      <Link href="/auth/login">
        <Button variant="secondary" className="w-full">{t("auth.backToLogin")}</Button>
      </Link>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <AuthCard>
      <Suspense
        fallback={
          <div className="text-center animate-pulse">
            <div className="w-12 h-12 bg-surface-2 rounded-full mx-auto mb-4" />
            <div className="h-6 bg-surface-2 rounded w-48 mx-auto mb-2" />
            <div className="h-4 bg-surface-2 rounded w-64 mx-auto" />
          </div>
        }
      >
        <VerifyEmailContent />
      </Suspense>
    </AuthCard>
  );
}

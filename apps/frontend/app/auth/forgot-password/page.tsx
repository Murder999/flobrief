"use client";

import { Button } from "@/components/ui/button";
import { AuthCard } from "@/components/auth/auth-card";
import { authApi, ApiError } from "@/lib/api-client";
import Link from "next/link";
import { type FormEvent, useState } from "react";
import { ArrowLeft, Mail, AlertCircle } from "lucide-react";
import { useLocale } from "@/context/locale-context";

export default function ForgotPasswordPage() {
  const { t } = useLocale();
  const [email,     setEmail]     = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sent,      setSent]      = useState(false);
  const [error,     setError]     = useState<string | null>(null);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setIsLoading(true);
    try {
      await authApi.forgotPassword(email);
      setSent(true);
    } catch (err) {
      if (err instanceof ApiError && err.status !== 422) {
        setSent(true);
      } else {
        setError(t("auth.error.invalidFields"));
      }
    } finally {
      setIsLoading(false);
    }
  }

  if (sent) {
    return (
      <AuthCard>
        <div className="text-center">
          <div className="w-12 h-12 bg-success/10 border border-success/20 rounded-2xl flex items-center justify-center mx-auto mb-5">
            <Mail className="w-6 h-6 text-success" />
          </div>
          <h2 className="text-xl font-bold text-text mb-2 tracking-tight">{t("auth.forgot.sentTitle")}</h2>
          <p className="text-sm text-text-muted mb-6 leading-relaxed">
            {t("auth.forgot.sentBody", { email })}
          </p>
          <Link href="/auth/login">
            <Button variant="secondary" className="w-full">
              {t("auth.backToLogin")}
            </Button>
          </Link>
        </div>
      </AuthCard>
    );
  }

  return (
    <AuthCard>
      <>
        <div className="mb-6">
          <Link
            href="/auth/login"
            className="inline-flex items-center gap-1.5 text-xs text-text-muted hover:text-accent transition-colors mb-4"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            {t("auth.backToLogin")}
          </Link>
          <h1 className="text-2xl font-bold text-text tracking-tight mb-1.5">{t("auth.forgot.title")}</h1>
          <p className="text-sm text-text-muted leading-relaxed">
            {t("auth.forgot.subtitle")}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="block text-xs font-medium text-text-muted" htmlFor="fp-email">
              {t("auth.fields.email")}
            </label>
            <input
              id="fp-email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-surface border border-border rounded-xl px-4 py-3 text-sm text-text placeholder:text-text-placeholder focus:outline-none focus:border-accent focus:shadow-accent transition-all"
              placeholder="siz@ajans.com"
            />
          </div>

          {error && (
            <div
              role="alert"
              className="flex items-start gap-2.5 rounded-xl bg-danger/8 border border-danger/20 px-4 py-3"
            >
              <AlertCircle className="w-4 h-4 text-danger flex-shrink-0 mt-0.5" />
              <p className="text-sm text-danger">{error}</p>
            </div>
          )}

          <Button type="submit" className="w-full" isLoading={isLoading}>
            {t("auth.forgot.send")}
          </Button>
        </form>
      </>
    </AuthCard>
  );
}

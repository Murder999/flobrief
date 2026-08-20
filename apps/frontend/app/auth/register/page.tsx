"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PhoneNumberInput } from "@/components/forms/PhoneNumberInput";
import { AuthCard } from "@/components/auth/auth-card";
import { useAuth } from "@/hooks/useAuth";
import { ApiError } from "@/lib/api-client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { useLocale } from "@/context/locale-context";

export default function RegisterPage() {
  const { register, isLoading } = useAuth();
  const { locale, t } = useLocale();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [whatsappOptIn, setWhatsappOptIn] = useState(false);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const hasPhone = phone.length > 0;

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setPhoneError(null);

    if (password !== confirmPassword) {
      setError(t("auth.password.mismatch"));
      return;
    }

    // Validate phone format if provided
    if (phone && !/^\+[1-9]\d{6,14}$/.test(phone)) {
      setPhoneError(t("auth.password.invalidPhone"));
      return;
    }

    try {
      await register({
        email,
        full_name: fullName,
        password,
        phone_number: phone || null,
        whatsapp_opt_in: phone ? whatsappOptIn : false,
      });
      setSuccess(true);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setError(t("auth.error.emailExists"));
        } else if (err.status === 422) {
          setError(t("auth.error.invalidFields"));
        } else {
          setError(err.message);
        }
      } else {
        setError(t("auth.error.generic"));
      }
    }
  }

  if (success) {
    return (
      <AuthCard>
        <div className="text-center">
          <div className="w-12 h-12 bg-success/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-6 h-6 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-text mb-2">{t("auth.register.createdTitle")}</h2>
          <p className="text-sm text-text-muted mb-6">
            {t("auth.register.createdBody", { email })}
          </p>
          <Button variant="secondary" className="w-full" onClick={() => router.push("/auth/login")}>
            {t("auth.register.goToLogin")}
          </Button>
        </div>
      </AuthCard>
    );
  }

  return (
    <AuthCard>
      <>
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-text">{t("auth.register.title")}</h1>
          <p className="mt-1 text-sm text-text-muted">
            {t("auth.register.subtitle")}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label={t("auth.fields.fullName")}
            type="text"
            placeholder={t("auth.fields.fullName")}
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
            autoComplete="name"
          />

          <Input
            label={t("auth.fields.email")}
            type="email"
            placeholder="siz@ajans.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />

          <PhoneNumberInput
            id="register-phone"
            label={t("auth.fields.phone")}
            value={phone}
            onChange={(e164) => {
              setPhone(e164);
              setPhoneError(null);
              if (!e164) setWhatsappOptIn(false);
            }}
            defaultCountry={locale === "tr" ? "TR" : "US"}
            error={phoneError ?? undefined}
            helperText={t("auth.phone.helper")}
          />

          {/* WhatsApp opt-in */}
          <div
            className={`flex items-start gap-3 rounded-xl border px-4 py-3 transition-colors ${
              hasPhone
                ? "border-border bg-surface-2"
                : "border-border/40 bg-surface-2/40 opacity-50"
            }`}
          >
            <div className="relative flex items-center justify-center mt-0.5 flex-shrink-0">
              <input
                type="checkbox"
                id="whatsapp_opt_in"
                checked={whatsappOptIn}
                disabled={!hasPhone}
                onChange={(e) => setWhatsappOptIn(e.target.checked)}
                className="sr-only peer"
              />
              <div
                onClick={() => hasPhone && setWhatsappOptIn((v) => !v)}
                className={`w-4 h-4 rounded border-2 flex items-center justify-center cursor-pointer transition-colors ${
                  whatsappOptIn && hasPhone
                    ? "bg-accent border-accent"
                    : "bg-surface border-border"
                } ${!hasPhone ? "cursor-not-allowed" : ""}`}
              >
                {whatsappOptIn && hasPhone && (
                  <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </div>
            </div>
            <label
              htmlFor="whatsapp_opt_in"
              className={`text-sm cursor-pointer select-none ${hasPhone ? "text-text" : "text-text-muted cursor-not-allowed"}`}
              onClick={() => hasPhone && setWhatsappOptIn((v) => !v)}
            >
              {t("auth.whatsapp.optIn")}
              <span className="block text-xs text-text-muted mt-0.5 leading-relaxed">
                {t("auth.whatsapp.detail")}
                {!hasPhone && (
                  <span className="block mt-0.5 italic">{t("auth.whatsapp.phoneRequired")}</span>
                )}
              </span>
            </label>
          </div>

          <Input
            label={t("auth.fields.password")}
            type="password"
            placeholder="••••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="new-password"
          />

          <Input
            label={t("auth.fields.confirmPassword")}
            type="password"
            placeholder="••••••••••"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            autoComplete="new-password"
          />

          <div className="bg-surface-2 rounded-lg px-4 py-3">
            <p className="text-xs font-medium text-text-muted mb-2">{t("auth.password.requirements")}</p>
            <ul className="space-y-1">
              {["auth.password.minTen", "auth.password.mixedCase", "auth.password.number", "auth.password.special"].map((key) => {
                const hint = t(key as "auth.password.minTen");
                return (
                <li key={hint} className="flex items-center gap-2 text-xs text-text-muted">
                  <span className="w-1 h-1 bg-text-muted rounded-full flex-shrink-0" />
                  {hint}
                </li>
                );
              })}
            </ul>
          </div>

          {error && (
            <div className="rounded-lg bg-danger/10 border border-danger/20 px-4 py-3">
              <p className="text-sm text-danger">{error}</p>
            </div>
          )}

          <Button type="submit" className="w-full" isLoading={isLoading}>
            {t("auth.actions.register")}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-text-muted">
          {t("auth.register.haveAccount")}{" "}
          <Link href="/auth/login" className="text-accent hover:text-accent-hover font-medium">
            {t("auth.register.loginLink")}
          </Link>
        </p>

        <p className="mt-4 text-center text-xs text-text-muted">
          {t("auth.register.termsPrefix")}{" "}
          <span className="text-text-muted underline cursor-pointer">{t("auth.register.terms")}</span>
          {" "}{t("auth.register.and")}{" "}
          <span className="text-text-muted underline cursor-pointer">{t("auth.register.privacy")}</span>.
        </p>
      </>
    </AuthCard>
  );
}

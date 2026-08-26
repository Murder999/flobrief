"use client";

import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { PostPiloterLogo } from "@/components/brand/PostPiloterLogo";
import { PhoneNumberInput } from "@/components/forms/PhoneNumberInput";
import { LanguageSelector } from "@/components/i18n/language-selector";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useLocale } from "@/context/locale-context";
import { useAuth } from "@/hooks/useAuth";
import {
  ApiError,
  invitationApi,
  type InvitationPreview,
} from "@/lib/api-client";
import type { TranslationKey } from "@/messages";

const ROLE_KEYS: Record<string, TranslationKey> = {
  owner: "auth.invite.role.owner",
  admin: "auth.invite.role.admin",
  brand_manager: "auth.invite.role.brand_manager",
  designer: "auth.invite.role.designer",
  developer: "auth.invite.role.developer",
  social_media_manager: "auth.invite.role.social_media_manager",
  viewer: "auth.invite.role.viewer",
  brand_owner: "auth.invite.role.brand_owner",
  brand_viewer: "auth.invite.role.brand_viewer",
  external_approver: "auth.invite.role.external_approver",
};

type PageState = "loading" | "ready" | "error" | "success";

function getInvitationErrorCode(error: unknown): string | null {
  if (!(error instanceof ApiError) || !error.detail || typeof error.detail !== "object") {
    return null;
  }
  const body = error.detail as Record<string, unknown>;
  const detail = body.detail;
  if (!detail || typeof detail !== "object") return null;
  const code = (detail as Record<string, unknown>).code;
  return typeof code === "string" ? code : null;
}

function StatusIcon({ tone }: { tone: "success" | "warning" | "danger" }) {
  const classes = {
    success: "border-success/20 bg-success/10 text-success",
    warning: "border-warning/20 bg-warning/10 text-warning",
    danger: "border-danger/20 bg-danger/10 text-danger",
  }[tone];
  return (
    <div className={`flex h-14 w-14 items-center justify-center rounded-2xl border ${classes}`}>
      {tone === "success" ? (
        <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="m5 13 4 4L19 7" />
        </svg>
      ) : (
        <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v4m0 4h.01M10.3 4.3 2.9 17.1A2 2 0 0 0 4.6 20h14.8a2 2 0 0 0 1.7-2.9L13.7 4.3a2 2 0 0 0-3.4 0Z" />
        </svg>
      )}
    </div>
  );
}

function InvitationShell({ children }: { children: React.ReactNode }) {
  return (
    <main className="relative min-h-screen overflow-hidden bg-background px-4 py-8 sm:py-12">
      <div className="pointer-events-none absolute left-1/2 top-[-18rem] h-[38rem] w-[38rem] -translate-x-1/2 rounded-full bg-accent/8 blur-3xl" />
      <div className="relative mx-auto w-full max-w-xl">
        <div className="mb-6 flex items-center justify-between">
          <PostPiloterLogo className="h-9 w-auto" priority />
          <LanguageSelector compact />
        </div>
        <section className="rounded-3xl border border-border bg-surface shadow-[0_32px_80px_rgba(15,23,42,0.12)]">
          {children}
        </section>
      </div>
    </main>
  );
}

export default function InvitationPage() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();
  const { locale, intlLocale, t } = useLocale();
  const {
    user,
    accessToken,
    isInitialized,
    isLoading: authLoading,
    logoutTo,
    refreshSession,
  } = useAuth();
  const [preview, setPreview] = useState<InvitationPreview | null>(null);
  const [pageState, setPageState] = useState<PageState>("loading");
  const [action, setAction] = useState<"signup" | "activate" | "accept" | "logout" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [whatsappOptIn, setWhatsappOptIn] = useState(false);
  const [password, setPassword] = useState("");
  const [passwordConfirmation, setPasswordConfirmation] = useState("");

  const returnTo = `/invite/${token}`;

  const loadPreview = useCallback(async () => {
    if (!token) {
      setPageState("error");
      return;
    }
    setPageState("loading");
    try {
      setPreview(await invitationApi.getPreview(token));
      setPageState("ready");
    } catch {
      setPageState("error");
    }
  }, [token]);

  useEffect(() => {
    void loadPreview();
  }, [loadPreview]);

  const targetRedirect = preview?.invitation_type === "brand" ? "/brand/dashboard" : "/dashboard";
  const expectedUserType = preview?.invitation_type === "brand" ? "brand_user" : "agency_user";
  const wrongAccount = Boolean(
    preview && user && user.email.toLowerCase() !== preview.email.toLowerCase()
  );
  const incompatibleLoggedIn = Boolean(
    preview && user && !wrongAccount && user.user_type !== expectedUserType
  );
  const expiry = useMemo(
    () =>
      preview
        ? new Intl.DateTimeFormat(intlLocale, {
            dateStyle: "medium",
            timeStyle: "short",
          }).format(new Date(preview.expires_at))
        : "",
    [intlLocale, preview]
  );

  async function handleSignup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!preview || action) return;
    setActionError(null);
    if (password !== passwordConfirmation) {
      setActionError(t("auth.password.mismatch"));
      return;
    }
    if (phone && !/^\+[1-9]\d{6,14}$/.test(phone)) {
      setActionError(t("auth.password.invalidPhone"));
      return;
    }
    setAction("signup");
    try {
      const result = await invitationApi.signup(token, {
        full_name: fullName,
        password,
        password_confirmation: passwordConfirmation,
        phone_number: phone || null,
        whatsapp_opt_in: phone ? whatsappOptIn : false,
        locale,
      });
      await refreshSession();
      setPageState("success");
      window.setTimeout(() => window.location.replace(result.redirect_to), 1200);
    } catch (error) {
      const code = getInvitationErrorCode(error);
      if (code === "INVITATION_ACCOUNT_EXISTS" || code?.startsWith("INVITATION_")) {
        await loadPreview();
      }
      setActionError(t("auth.invite.acceptFailed"));
    } finally {
      setAction(null);
    }
  }

  async function handleAccept() {
    if (!preview || !accessToken || action) return;
    setAction("accept");
    setActionError(null);
    try {
      await invitationApi.accept(token, accessToken);
      setPageState("success");
      window.setTimeout(() => window.location.replace(targetRedirect), 1200);
    } catch (error) {
      const code = getInvitationErrorCode(error);
      if (code === "INVITATION_ACCOUNT_TYPE_CONFLICT") {
        setActionError(t("auth.invite.incompatibleBody"));
      } else {
        await loadPreview();
        setActionError(t("auth.invite.acceptFailed"));
      }
    } finally {
      setAction(null);
    }
  }

  async function handleExistingAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!preview || action) return;
    setAction("activate");
    setActionError(null);
    try {
      const result = await invitationApi.activate(token, { password });
      await refreshSession();
      setPageState("success");
      window.setTimeout(() => window.location.replace(result.redirect_to), 1200);
    } catch (error) {
      const code = getInvitationErrorCode(error);
      if (code === "INVITATION_INVALID_CREDENTIALS") {
        setActionError(t("auth.error.invalidCredentials"));
      } else if (code === "INVITATION_ACCOUNT_NOT_FOUND") {
        await loadPreview();
        setActionError(t("auth.invite.acceptFailed"));
      } else {
        setActionError(t("auth.invite.activationFailed"));
      }
    } finally {
      setAction(null);
    }
  }

  async function handleCorrectAccount() {
    if (action) return;
    setAction("logout");
    await logoutTo(returnTo);
  }

  if (pageState === "loading") {
    return (
      <InvitationShell>
        <div className="flex min-h-[26rem] flex-col items-center justify-center gap-4 p-8" role="status">
          <div className="h-9 w-9 animate-spin rounded-full border-2 border-accent/20 border-t-accent" />
          <p className="text-sm text-text-muted">{t("auth.invite.loading")}</p>
        </div>
      </InvitationShell>
    );
  }

  if (pageState === "error" || !preview) {
    return (
      <InvitationShell>
        <div className="flex min-h-[26rem] flex-col items-center justify-center px-6 py-12 text-center">
          <StatusIcon tone="danger" />
          <h1 className="mt-5 text-xl font-bold text-text">{t("auth.invite.serverTitle")}</h1>
          <p className="mt-2 max-w-sm text-sm leading-6 text-text-muted">{t("auth.invite.serverBody")}</p>
          <Button className="mt-6" variant="secondary" onClick={() => void loadPreview()}>
            {t("auth.invite.retry")}
          </Button>
        </div>
      </InvitationShell>
    );
  }

  if (pageState === "success") {
    return (
      <InvitationShell>
        <div className="flex min-h-[26rem] flex-col items-center justify-center px-6 py-12 text-center" role="status">
          <StatusIcon tone="success" />
          <h1 className="mt-5 text-xl font-bold text-text">{t("auth.invite.acceptedTitle")}</h1>
          <p className="mt-2 text-sm text-text-muted">{t("auth.invite.successBody")}</p>
          <p className="mt-1 text-xs text-text-muted">{t("auth.invite.redirecting")}</p>
        </div>
      </InvitationShell>
    );
  }

  if (preview.state !== "pending") {
    const terminal = {
      accepted: ["auth.invite.acceptedTitle", "auth.invite.acceptedBody", "success"],
      expired: ["auth.invite.expiredTitle", "auth.invite.expiredBody", "warning"],
      revoked: ["auth.invite.revokedTitle", "auth.invite.revokedBody", "warning"],
      declined: ["auth.invite.declinedTitle", "auth.invite.declinedStateBody", "warning"],
    }[preview.state] as [TranslationKey, TranslationKey, "success" | "warning"];
    return (
      <InvitationShell>
        <div className="flex min-h-[26rem] flex-col items-center justify-center px-6 py-12 text-center">
          <StatusIcon tone={terminal[2]} />
          <h1 className="mt-5 text-xl font-bold text-text">{t(terminal[0])}</h1>
          <p className="mt-2 max-w-sm text-sm leading-6 text-text-muted">{t(terminal[1])}</p>
          <Button className="mt-6" variant="secondary" onClick={() => router.push("/")}>
            {t("auth.invite.home")}
          </Button>
        </div>
      </InvitationShell>
    );
  }

  const roleKey = ROLE_KEYS[preview.role];
  const roleLabel = roleKey ? t(roleKey) : preview.role;
  const isExistingConflict = preview.account_exists && preview.account_type_compatible === false;

  return (
    <InvitationShell>
      <header className="border-b border-border px-6 py-7 sm:px-8">
        <div className="inline-flex rounded-full border border-accent/20 bg-accent/8 px-3 py-1 text-xs font-semibold text-accent">
          {preview.invitation_type === "brand"
            ? t("auth.invite.brandPortal", { brand: preview.brand_name ?? "PostPiloter" })
            : t("auth.invite.receivedTitle")}
        </div>
        <h1 className="mt-4 text-2xl font-bold tracking-tight text-text">
          {t("auth.invite.invitedBy", { agency: preview.agency_name })}
        </h1>
        <p className="mt-2 text-sm leading-6 text-text-muted">
          {preview.invitation_type === "brand"
            ? t("auth.invite.brandContext", {
                agency: preview.agency_name,
                brand: preview.brand_name ?? "PostPiloter",
              })
            : t("auth.invite.agencyContext", { agency: preview.agency_name })}
        </p>
      </header>

      <div className="space-y-6 px-6 py-7 sm:px-8">
        <dl className="grid gap-3 rounded-2xl border border-border bg-background/70 p-4 sm:grid-cols-3">
          <div className="min-w-0">
            <dt className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">{t("auth.invite.invitedEmail")}</dt>
            <dd className="mt-1 truncate text-sm font-medium text-text" title={preview.email}>{preview.email}</dd>
          </div>
          <div>
            <dt className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">{t("auth.invite.role")}</dt>
            <dd className="mt-1 text-sm font-medium text-text">{roleLabel}</dd>
          </div>
          <div>
            <dt className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">{t("auth.invite.expiration")}</dt>
            <dd className="mt-1 text-sm font-medium text-text">{expiry}</dd>
          </div>
        </dl>

        {(!isInitialized || authLoading) && (
          <div className="flex items-center justify-center gap-3 py-8 text-sm text-text-muted" role="status">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-accent/20 border-t-accent" />
            {t("auth.invite.loading")}
          </div>
        )}

        {isInitialized && !authLoading && wrongAccount && (
          <div className="rounded-2xl border border-warning/25 bg-warning/8 p-5" role="alert">
            <h2 className="font-semibold text-text">{t("auth.invite.wrongAccountTitle")}</h2>
            <p className="mt-2 text-sm leading-6 text-text-muted">{t("auth.invite.wrongAccountBody", { email: preview.email })}</p>
            <Button className="mt-5 w-full" variant="secondary" isLoading={action === "logout"} onClick={() => void handleCorrectAccount()}>
              {t("auth.invite.logoutCorrectAccount")}
            </Button>
          </div>
        )}

        {isInitialized && !authLoading && !wrongAccount && (incompatibleLoggedIn || isExistingConflict) && (
          <div className="rounded-2xl border border-warning/25 bg-warning/8 p-5" role="alert">
            <h2 className="font-semibold text-text">{t("auth.invite.incompatibleTitle")}</h2>
            <p className="mt-2 text-sm leading-6 text-text-muted">{t("auth.invite.incompatibleBody")}</p>
          </div>
        )}

        {isInitialized && !authLoading && !wrongAccount && !incompatibleLoggedIn && user && (
          <div className="rounded-2xl border border-accent/20 bg-accent/5 p-5">
            <p className="text-sm text-text-muted">{t("auth.invite.account", { email: user.email })}</p>
            <Button className="mt-4 w-full" isLoading={action === "accept"} onClick={() => void handleAccept()}>
              {t("auth.invite.accept")}
            </Button>
          </div>
        )}

        {isInitialized && !authLoading && !user && preview.account_exists && preview.account_type_compatible !== false && (
          <form className="space-y-4 rounded-2xl border border-accent/20 bg-accent/5 p-5" onSubmit={handleExistingAccount} aria-busy={action === "activate"}>
            <h2 className="font-semibold text-text">{t("auth.invite.existingTitle")}</h2>
            <p className="text-sm leading-6 text-text-muted">{t("auth.invite.existingBody", { role: roleLabel })}</p>
            <Input label={t("auth.fields.email")} type="email" value={preview.email} readOnly aria-readonly="true" />
            <Input label={t("auth.fields.password")} type="password" value={password} onChange={(event) => setPassword(event.target.value)} required autoComplete="current-password" />
            <div className="flex justify-end">
              <Link className="text-xs font-medium text-accent hover:text-accent-hover" href="/auth/forgot-password">
                {t("auth.password.forgot")}
              </Link>
            </div>
            {actionError && <div className="rounded-xl border border-danger/20 bg-danger/8 px-4 py-3 text-sm text-danger" role="alert">{actionError}</div>}
            <Button className="w-full" type="submit" isLoading={action === "activate"}>
              {t("auth.invite.loginAndAccept")}
            </Button>
          </form>
        )}

        {isInitialized && !authLoading && !user && preview.account_exists === false && (
          <form className="space-y-4" onSubmit={handleSignup} aria-busy={action === "signup"}>
            <div>
              <h2 className="text-lg font-bold text-text">{t("auth.invite.createTitle")}</h2>
              <p className="mt-1 text-sm text-text-muted">{t("auth.invite.createBody")}</p>
            </div>
            <Input label={t("auth.fields.email")} type="email" value={preview.email} readOnly aria-readonly="true" />
            <p className="-mt-2 text-xs text-text-muted">{t("auth.invite.lockedEmail")}</p>
            <Input label={t("auth.fields.fullName")} value={fullName} onChange={(event) => setFullName(event.target.value)} required autoComplete="name" />
            <PhoneNumberInput
              id="invite-phone"
              label={t("auth.invite.phoneOptional")}
              value={phone}
              onChange={(value) => {
                setPhone(value);
                if (!value) setWhatsappOptIn(false);
              }}
              defaultCountry={locale === "tr" ? "TR" : "US"}
            />
            <label className={`flex items-start gap-3 rounded-xl border border-border bg-background/70 p-4 ${phone ? "cursor-pointer" : "opacity-50"}`}>
              <input
                className="mt-1 h-4 w-4 rounded border-border accent-accent"
                type="checkbox"
                checked={whatsappOptIn}
                disabled={!phone}
                onChange={(event) => setWhatsappOptIn(event.target.checked)}
              />
              <span className="text-sm text-text">
                {t("auth.whatsapp.optIn")}
                <span className="mt-1 block text-xs leading-5 text-text-muted">{t("auth.whatsapp.detail")}</span>
              </span>
            </label>
            <Input label={t("auth.fields.password")} type="password" value={password} onChange={(event) => setPassword(event.target.value)} required autoComplete="new-password" />
            <Input label={t("auth.fields.confirmPassword")} type="password" value={passwordConfirmation} onChange={(event) => setPasswordConfirmation(event.target.value)} required autoComplete="new-password" />
            <p className="text-xs leading-5 text-text-muted">{t("auth.invite.passwordHint")}</p>
            {actionError && <div className="rounded-xl border border-danger/20 bg-danger/8 px-4 py-3 text-sm text-danger" role="alert">{actionError}</div>}
            <Button className="w-full" type="submit" isLoading={action === "signup"}>
              {t("auth.invite.createAccept")}
            </Button>
          </form>
        )}

        {actionError && user && (
          <div className="rounded-xl border border-danger/20 bg-danger/8 px-4 py-3 text-sm text-danger" role="alert">{actionError}</div>
        )}
      </div>
    </InvitationShell>
  );
}

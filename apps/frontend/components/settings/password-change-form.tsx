"use client";

import { useId, useState, type FormEvent } from "react";
import { Eye, EyeOff, KeyRound, ShieldCheck } from "lucide-react";
import { authApi, platformAuthApi } from "@/lib/api-client";
import { useLocale } from "@/context/locale-context";
import type { TranslationKey } from "@/messages";

type PasswordChangeFormProps = {
  accessToken: string | null;
  mode?: "user" | "platform";
  onCompleted?: () => void;
};

const PASSWORD_RULES = [
  { labelKey: "settings.password.rule.length" as TranslationKey, test: (value: string) => value.length >= 10 },
  { labelKey: "settings.password.rule.case" as TranslationKey, test: (value: string) => /[A-Z]/.test(value) && /[a-z]/.test(value) },
  { labelKey: "settings.password.rule.number" as TranslationKey, test: (value: string) => /\d/.test(value) },
  { labelKey: "settings.password.rule.special" as TranslationKey, test: (value: string) => /[^a-zA-Z0-9]/.test(value) },
];

function PasswordInput({
  id,
  label,
  value,
  onChange,
  autoComplete,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: "current-password" | "new-password";
}) {
  const { t } = useLocale();
  const [visible, setVisible] = useState(false);
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-text mb-1.5">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type={visible ? "text" : "password"}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          autoComplete={autoComplete}
          required
          className="w-full h-10 rounded-lg border border-border bg-background px-3 pr-10 text-sm text-text outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/20"
        />
        <button
          type="button"
          onClick={() => setVisible((current) => !current)}
          aria-label={t(visible ? "settings.password.hide" : "settings.password.show", { label })}
          className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-text-muted transition hover:text-text focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
        >
          {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
    </div>
  );
}

export function PasswordChangeForm({
  accessToken,
  mode = "user",
  onCompleted,
}: PasswordChangeFormProps) {
  const { t } = useLocale();
  const id = useId();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const rulesPass = PASSWORD_RULES.every((rule) => rule.test(newPassword));
  const passwordsMatch = confirmation.length > 0 && newPassword === confirmation;
  const canSubmit = Boolean(
    accessToken && currentPassword && rulesPass && passwordsMatch && currentPassword !== newPassword
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!accessToken || !canSubmit) return;
    setSubmitting(true);
    setError(null);
    setSuccess(false);
    try {
      const payload = { current_password: currentPassword, new_password: newPassword };
      if (mode === "platform") {
        await platformAuthApi.changePassword(payload, accessToken);
      } else {
        await authApi.changePassword(payload, accessToken);
      }
      setCurrentPassword("");
      setNewPassword("");
      setConfirmation("");
      setSuccess(true);
      window.setTimeout(() => onCompleted?.(), 1200);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("settings.password.error"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="rounded-2xl border border-border bg-surface p-6" aria-labelledby={`${id}-title`}>
      <div className="mb-5 flex items-start gap-3">
        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-accent/10 text-accent">
          <KeyRound className="h-5 w-5" />
        </div>
        <div>
          <h2 id={`${id}-title`} className="text-sm font-semibold text-text">{t("settings.password.title")}</h2>
          <p className="mt-1 text-xs leading-relaxed text-text-muted">
            {t("settings.password.description")}
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <PasswordInput
          id={`${id}-current`}
          label={t("settings.password.current")}
          value={currentPassword}
          onChange={setCurrentPassword}
          autoComplete="current-password"
        />
        <PasswordInput
          id={`${id}-new`}
          label={t("settings.password.new")}
          value={newPassword}
          onChange={setNewPassword}
          autoComplete="new-password"
        />
        <PasswordInput
          id={`${id}-confirmation`}
          label={t("settings.password.confirm")}
          value={confirmation}
          onChange={setConfirmation}
          autoComplete="new-password"
        />

        <div className="grid gap-2 rounded-xl border border-border/70 bg-surface-2 p-3 sm:grid-cols-2">
          {PASSWORD_RULES.map((rule) => {
            const passed = rule.test(newPassword);
            return (
              <div key={rule.labelKey} className={`flex items-center gap-2 text-xs ${passed ? "text-success" : "text-text-muted"}`}>
                <span className={`h-1.5 w-1.5 rounded-full ${passed ? "bg-success" : "bg-border-hover"}`} />
                {t(rule.labelKey)}
              </div>
            );
          })}
        </div>

        {confirmation && !passwordsMatch && (
          <p className="text-sm text-danger" role="alert">{t("settings.password.mismatch")}</p>
        )}
        {currentPassword && newPassword && currentPassword === newPassword && (
          <p className="text-sm text-danger" role="alert">{t("settings.password.same")}</p>
        )}
        {error && (
          <div className="rounded-lg border border-danger/20 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">
            {error}
          </div>
        )}
        {success && (
          <div className="flex items-center gap-2 rounded-lg border border-success/20 bg-success/10 px-4 py-3 text-sm text-success" role="status">
            <ShieldCheck className="h-4 w-4" />
            {t("settings.password.success")}
          </div>
        )}

        <button
          type="submit"
          disabled={!canSubmit || submitting || success}
          className="inline-flex h-10 items-center justify-center rounded-lg bg-accent px-5 text-sm font-medium text-white transition hover:bg-accent/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {t(submitting ? "settings.password.updating" : "settings.password.submit")}
        </button>
      </form>
    </section>
  );
}

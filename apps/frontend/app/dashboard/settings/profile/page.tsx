"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { authApi } from "@/lib/api-client";
import { PhoneNumberInput } from "@/components/forms/PhoneNumberInput";
import { PasswordChangeForm } from "@/components/settings/password-change-form";
import { applyTheme, getTheme, type Theme } from "@/lib/theme";
import { LanguageSelector } from "@/components/i18n/language-selector";
import { useLocale } from "@/context/locale-context";
import { formatLocalizedDate } from "@/lib/i18n/format";

function formatDate(iso: string | null, locale: "en" | "tr"): string {
  if (!iso) return "—";
  return formatLocalizedDate(iso, locale, {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export default function ProfilePage() {
  const { locale, t } = useLocale();
  const { user, accessToken, refreshUser, logout } = useAuth();
  const [currentTheme, setCurrentTheme] = useState<Theme>("system");

  // Editable profile state
  const [fullName, setFullName] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Phone number only — WhatsApp consent itself is granted from the
  // Notifications settings panel (/dashboard/settings/notifications), never
  // implied by phone presence.
  const [phoneNumber, setPhoneNumber] = useState("");
  const [savingWhatsApp, setSavingWhatsApp] = useState(false);
  const [whatsAppSaveError, setWhatsAppSaveError] = useState<string | null>(null);
  const [whatsAppSaveSuccess, setWhatsAppSaveSuccess] = useState(false);

  const [avatarUploading, setAvatarUploading] = useState(false);
  const [avatarError, setAvatarError] = useState<string | null>(null);

  const handleAvatarSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !accessToken) return;
    setAvatarUploading(true);
    setAvatarError(null);
    try {
      await authApi.uploadAvatar(file, accessToken);
      if (refreshUser) await refreshUser();
    } catch (err: unknown) {
      const error = err as { message?: string };
      setAvatarError(error?.message ?? t("settings.profile.avatarUploadError"));
    } finally {
      setAvatarUploading(false);
    }
  };

  const handleAvatarRemove = async () => {
    if (!accessToken) return;
    setAvatarUploading(true);
    setAvatarError(null);
    try {
      await authApi.deleteAvatar(accessToken);
      if (refreshUser) await refreshUser();
    } catch (err: unknown) {
      const error = err as { message?: string };
      setAvatarError(error?.message ?? t("settings.profile.avatarRemoveError"));
    } finally {
      setAvatarUploading(false);
    }
  };

  useEffect(() => {
    setCurrentTheme(getTheme());
  }, []);

  useEffect(() => {
    if (user) {
      setFullName(user.full_name ?? "");
      setJobTitle(user.job_title ?? "");
      setPhoneNumber(user.phone_number ?? "");
    }
  }, [user]);

  const handleThemeChange = (theme: Theme) => {
    setCurrentTheme(theme);
    applyTheme(theme);
  };

  const handleSaveProfile = async () => {
    if (!accessToken || !fullName.trim()) return;
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(false);
    try {
      await authApi.updateProfile(
        { full_name: fullName.trim(), job_title: jobTitle.trim() || null },
        accessToken
      );
      if (refreshUser) await refreshUser();
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (e: unknown) {
      const err = e as { message?: string };
      setSaveError(err?.message ?? t("settings.profile.saveError"));
    } finally {
      setSaving(false);
    }
  };

  const THEME_OPTIONS: { value: Theme; label: string; description: string; iconPath: string }[] = [
    {
      value: "dark",
      label: t("settings.theme.dark"),
      description: t("settings.theme.darkDescription"),
      iconPath: "M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z",
    },
    {
      value: "light",
      label: t("settings.theme.light"),
      description: t("settings.theme.lightDescription"),
      iconPath: "M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z",
    },
    {
      value: "system",
      label: t("settings.theme.system"),
      description: t("settings.theme.systemDescription"),
      iconPath: "M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z",
    },
  ];

  const handleSaveWhatsApp = async () => {
    if (!accessToken) return;
    setSavingWhatsApp(true);
    setWhatsAppSaveError(null);
    setWhatsAppSaveSuccess(false);
    try {
      await authApi.updateProfile(
        { phone_number: phoneNumber.trim() || null },
        accessToken
      );
      if (refreshUser) await refreshUser();
      setWhatsAppSaveSuccess(true);
      setTimeout(() => setWhatsAppSaveSuccess(false), 3000);
    } catch (e: unknown) {
      const err = e as { message?: string };
      setWhatsAppSaveError(err?.message ?? t("settings.profile.saveError"));
    } finally {
      setSavingWhatsApp(false);
    }
  };

  const isDirty = fullName !== (user?.full_name ?? "") || jobTitle !== (user?.job_title ?? "");
  const isWhatsAppDirty = phoneNumber !== (user?.phone_number ?? "");

  return (
    <div>
      {/* Section: Profil Bilgileri */}
      <section className="mb-6 rounded-2xl border border-border bg-surface p-5">
        <div className="flex items-center gap-5 mb-5">
          <div className="relative flex-shrink-0 group/avatar">
            {user?.avatar_url ? (
              <img
                src={user.avatar_url}
                alt={user.full_name}
                className="w-16 h-16 rounded-full object-cover border border-border"
              />
            ) : (
              <div className="w-16 h-16 bg-accent/20 rounded-full flex items-center justify-center">
                <span className="text-xl font-bold text-accent">
                  {user?.full_name
                    ?.split(" ")
                    .map((w) => w[0])
                    .join("")
                    .slice(0, 2)
                    .toUpperCase() ?? "?"}
                </span>
              </div>
            )}
            <label
              className="absolute inset-0 flex items-center justify-center rounded-full bg-black/50 opacity-0 group-hover/avatar:opacity-100 transition-opacity cursor-pointer text-white text-[10px] font-medium"
              title={t("settings.profile.changeAvatar")}
            >
              {avatarUploading ? "…" : t("settings.profile.change")}
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                className="hidden"
                disabled={avatarUploading}
                onChange={handleAvatarSelect}
              />
            </label>
          </div>
          <div>
            <h2 className="text-lg font-semibold text-text">{user?.full_name ?? "—"}</h2>
            <p className="text-sm text-text-muted">{user?.email ?? "—"}</p>
            {user?.job_title && (
              <p className="text-xs text-accent mt-0.5">{user.job_title}</p>
            )}
            {user?.avatar_url && (
              <button
                type="button"
                onClick={handleAvatarRemove}
                disabled={avatarUploading}
                className="text-xs text-text-muted hover:text-red-600 transition-colors mt-1 disabled:opacity-50"
              >
                {t("settings.profile.removeAvatar")}
              </button>
            )}
          </div>
        </div>

        {avatarError && (
          <div className="mb-3 p-2 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{avatarError}</div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-text mb-1.5">
              {t("settings.profile.fullName")} <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-text placeholder-text-muted/50 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
              placeholder={t("settings.profile.fullNamePlaceholder")}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-text mb-1.5">
              {t("settings.profile.jobTitle")}
            </label>
            <input
              type="text"
              value={jobTitle}
              onChange={(e) => setJobTitle(e.target.value)}
              className="w-full px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-text placeholder-text-muted/50 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
              placeholder={t("settings.profile.jobTitlePlaceholder")}
            />
            <p className="text-xs text-text-muted mt-1.5">
              {t("settings.profile.jobTitleHelp")}
            </p>
          </div>

          {saveError && (
            <div className="p-2 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{saveError}</div>
          )}

          {saveSuccess && (
            <div className="flex items-center gap-2 p-2 rounded-lg bg-emerald-500/10 border border-emerald-200 text-sm text-emerald-700">
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              {t("settings.profile.saved")}
            </div>
          )}

          <button
            onClick={handleSaveProfile}
            disabled={saving || !isDirty || !fullName.trim()}
            className="w-full px-5 py-2.5 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 disabled:opacity-50 transition-colors flex items-center gap-2"
          >
            {saving ? (
              <>
                <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="2" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                {t("settings.profile.saving")}
              </>
            ) : t("common.actions.save")}
          </button>
        </div>
      </section>

      {/* Section: Tercihler */}
      <section className="mb-6 rounded-2xl border border-border bg-surface p-5">
        <h3 className="text-sm font-semibold text-text mb-3">{t("settings.profile.language")}</h3>
        <p className="text-xs text-text-muted mb-4">{t("settings.profile.languageHelp")}</p>
        <LanguageSelector className="self-start sm:self-auto" />

        <h3 className="text-sm font-semibold text-text mb-3 mt-6">{t("settings.theme.title")}</h3>
        <p className="text-xs text-text-muted mb-4">{t("settings.theme.description")}</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {THEME_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => handleThemeChange(opt.value)}
              className={`flex flex-col items-center gap-2.5 p-4 rounded-xl border-2 transition-all ${
                currentTheme === opt.value
                  ? "border-accent bg-accent/10 text-accent"
                  : "border-border hover:border-border-hover text-text-muted hover:text-text"
              }`}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={opt.iconPath} />
              </svg>
              <div className="text-center">
                <p className="text-xs font-semibold">{opt.label}</p>
                <p className="text-[10px] mt-0.5 opacity-70">{opt.description}</p>
              </div>
              {currentTheme === opt.value && (
                <div className="w-3 h-3 rounded-full bg-accent flex items-center justify-center">
                  <svg className="w-1.5 h-1.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
              )}
            </button>
          ))}
        </div>
      </section>

      {/* Section: Account & Security */}
      <section className="rounded-2xl border border-border bg-surface p-5">
        <PasswordChangeForm accessToken={accessToken} onCompleted={() => void logout()} />

        <div className="mt-5 pt-5 border-t border-border">
          <h3 className="text-sm font-semibold text-text mb-2">{t("settings.security.mfaTitle")}</h3>
          <p className="text-xs text-text-muted">
            {user?.mfa_enabled
              ? t("settings.security.mfaEnabledDescription")
              : t("settings.security.mfaDisabledDescription")}
          </p>
          <div className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-current mr-1.5" />
            {t(user?.mfa_enabled ? "settings.security.enabled" : "settings.security.disabled")}
          </div>
        </div>

        <div className="mt-5 pt-5 border-t border-border">
          <h3 className="text-sm font-semibold text-text mb-2">{t("settings.whatsapp.title")}</h3>
          <p className="text-xs text-text-muted">
            {t("settings.whatsapp.description")}
          </p>
          <PhoneNumberInput
            id="profile-phone"
            label={t("settings.whatsapp.phone")}
            value={phoneNumber}
            onChange={(e164) => setPhoneNumber(e164)}
            defaultCountry="TR"
            helperText={t("settings.whatsapp.phoneHelp")}
          />

          <div className="flex items-center justify-between gap-3 rounded-xl border border-border bg-surface-2 px-4 py-3">
            <p className="text-xs text-text-muted leading-relaxed">
              {t("settings.whatsapp.preferencesHelp")}
            </p>
            <a
              href="/dashboard/settings/notifications"
              className="text-xs font-medium text-accent hover:underline whitespace-nowrap flex-shrink-0"
            >
              {t("settings.whatsapp.openPreferences")} →
            </a>
          </div>

          {whatsAppSaveError && (
            <div className="p-2 rounded-lg bg-danger/10 border border-danger/20 text-sm text-danger">{whatsAppSaveError}</div>
          )}
          {whatsAppSaveSuccess && (
            <div className="flex items-center gap-1.5 p-2 rounded-lg bg-emerald-500/10 border border-emerald-200 text-sm text-emerald-500">
              <svg className="w-3 h-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              {t("settings.whatsapp.saved")}
            </div>
          )}

          <button
            onClick={handleSaveWhatsApp}
            disabled={savingWhatsApp || !isWhatsAppDirty}
            className="w-full px-5 py-2.5 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 disabled:opacity-50 transition-colors flex items-center gap-2"
          >
            {savingWhatsApp ? (
              <>
                <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="2" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                {t("settings.profile.saving")}
              </>
            ) : t("settings.whatsapp.save")}
          </button>
        </div>
      </section>
    </div>
  );
}

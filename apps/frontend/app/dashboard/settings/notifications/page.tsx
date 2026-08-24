"use client";

import { WhatsAppPreferencesPanel } from "@/components/notifications/WhatsAppPreferencesPanel";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import {
  notificationApi,
  type NotificationPreferenceRead,
  type NotificationPreferenceUpdate,
} from "@/lib/api-client";
import { useEffect, useState } from "react";
import { InfoTooltip } from "@/components/contextual-help/InfoTooltip";
import { useLocale } from "@/context/locale-context";
import { useRef } from "react";

// ── Toggle row ────────────────────────────────────────────────────────────────

interface ToggleRowProps {
  label: string;
  description: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (value: boolean) => void;
  saving: boolean;
}

function ToggleRow({ label, description, checked, disabled, onChange, saving }: ToggleRowProps) {
  return (
    <div className="flex items-start justify-between py-3 border-b border-border last:border-b-0">
      <div className="flex-1 pr-4">
        <p className="text-sm font-medium text-text">{label}</p>
        <p className="text-xs text-text-muted mt-0.5 leading-relaxed">{description}</p>
      </div>
      <button
        role="switch"
        aria-checked={checked}
        disabled={disabled || saving}
        onClick={() => !disabled && !saving && onChange(!checked)}
        className={`relative inline-flex h-5 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-surface disabled:opacity-40 flex-shrink-0 ${
          checked && !disabled ? "bg-accent" : "bg-surface-2"
        }`}
      >
        <span
          className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow-sm transition-transform ${
            checked && !disabled ? "translate-x-5" : "translate-x-1"
          }`}
        />
      </button>
    </div>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function PreferenceSkeleton() {
  return (
    <div className="animate-pulse space-y-1">
      {[1, 2].map((i) => (
        <div key={i} className="flex items-start justify-between py-3 border-b border-border last:border-b-0">
          <div className="flex-1 pr-4 space-y-1">
            <div className="h-3 bg-surface-2 rounded w-24" />
            <div className="h-2 bg-surface-2 rounded w-36" />
          </div>
          <div className="h-5 w-9 bg-surface-2 rounded-full flex-shrink-0" />
        </div>
      ))}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function NotificationPreferencesPage() {
  const { t } = useLocale();
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();

  const [prefs, setPrefs] = useState<NotificationPreferenceRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const emailRef = useRef<HTMLDivElement>(null);
  const inAppRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!accessToken) return;
    notificationApi
      .getPreferences(accessToken)
      .then(setPrefs)
      .catch(() => setErrorMsg(t("settings.notifications.loadError")))
      .finally(() => setLoading(false));
  }, [accessToken, t]);

  const update = async (patch: NotificationPreferenceUpdate) => {
    if (!accessToken || !prefs) return;
    setSaving(true);
    setSuccessMsg(null);
    setErrorMsg(null);
    try {
      const updated = await notificationApi.updatePreferences(patch, accessToken);
      setPrefs(updated);
      setSuccessMsg(t("settings.notifications.saveSuccess"));
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch {
      setErrorMsg(t("settings.notifications.saveError"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      {/* Feedback banners */}
      {successMsg && (
        <div className="mb-3 bg-emerald-500/10 border border-emerald-200 rounded-xl px-3 py-2 text-sm text-emerald-400">
          {successMsg}
        </div>
      )}
      {errorMsg && (
        <div className="mb-3 bg-danger/10 border border-danger/30 rounded-xl px-3 py-2 text-sm text-danger">
          {errorMsg}
        </div>
      )}

      {/* Preferences grid - channel based compact layout */}
      <div className="space-y-4">
        {/* Email / in-app preferences card */}
        <div className="bg-surface border border-border rounded-xl p-4">
          {loading ? (
            <PreferenceSkeleton />
          ) : !prefs ? (
            <div className="py-6 text-center text-sm text-text-muted">
              {t("settings.notifications.loadError")}
            </div>
          ) : (
            <>
              <InfoTooltip
  targetRef={emailRef}
                text={t("settings.notifications.emailTooltip")}
                title={t("settings.notifications.emailTitle")}
              />
              <ToggleRow
                label={t("settings.notifications.emailTitle")}
                description={t("settings.notifications.emailDescription")}
                checked={prefs.email_enabled}
                saving={saving}
                onChange={(val) =>
                  update({
                    email_enabled: val,
                    whatsapp_enabled: prefs.whatsapp_enabled,
                    in_app_enabled: prefs.in_app_enabled,
                  })
                }
              />
              <InfoTooltip
                targetRef={inAppRef}
                text={t("settings.notifications.inAppTooltip")}
                title={t("settings.notifications.inAppTitle")}
              />
              <ToggleRow
                label={t("settings.notifications.inAppTitle")}
                description={t("settings.notifications.inAppDescription")}
                checked={prefs.in_app_enabled}
                saving={saving}
                onChange={(val) =>
                  update({
                    email_enabled: prefs.email_enabled,
                    whatsapp_enabled: prefs.whatsapp_enabled,
                    in_app_enabled: val,
                  })
                }
              />
            </>
          )}
        </div>

        {/* WhatsApp - compact status + preference switch */}
        <div className="bg-surface border border-border rounded-xl p-4">
          <h2 className="text-sm font-semibold text-text mb-2">
            {t("settings.notifications.whatsappTitle")}
          </h2>
          <WhatsAppPreferencesPanel
            accessToken={accessToken}
            agencyId={activeAgency?.id ?? null}
            portal="agency"
            phoneSettingsHref="/dashboard/settings/profile"
          />
        </div>
      </div>
    </div>
  );
}

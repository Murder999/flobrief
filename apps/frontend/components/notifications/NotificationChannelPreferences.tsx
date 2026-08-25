"use client";

import { InfoTooltip } from "@/components/contextual-help/InfoTooltip";
import { useLocale } from "@/context/locale-context";
import {
  notificationApi,
  type NotificationPreferenceRead,
  type NotificationPreferenceUpdate,
} from "@/lib/api-client";
import { useEffect, useRef, useState } from "react";

interface NotificationChannelPreferencesProps {
  accessToken: string | null;
  helpHref: string;
}

interface ToggleRowProps {
  label: string;
  description: string;
  checked: boolean;
  saving: boolean;
  onChange: (value: boolean) => void;
}

function ToggleRow({ label, description, checked, saving, onChange }: ToggleRowProps) {
  return (
    <div className="flex items-start justify-between border-b border-border py-3 last:border-b-0">
      <div className="flex-1 pr-4">
        <p className="text-sm font-medium text-text">{label}</p>
        <p className="mt-0.5 text-xs leading-relaxed text-text-muted">{description}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-label={label}
        aria-checked={checked}
        disabled={saving}
        onClick={() => !saving && onChange(!checked)}
        className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:opacity-40 ${
          checked ? "bg-accent" : "border border-border bg-surface-2"
        }`}
      >
        <span
          className={`inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform ${
            checked ? "translate-x-6" : "translate-x-1"
          }`}
        />
      </button>
    </div>
  );
}

function PreferenceSkeleton() {
  return (
    <div className="animate-pulse space-y-1">
      {[1, 2].map((item) => (
        <div key={item} className="flex items-start justify-between border-b border-border py-3 last:border-b-0">
          <div className="flex-1 space-y-1 pr-4">
            <div className="h-3 w-28 rounded bg-surface-2" />
            <div className="h-2 w-44 rounded bg-surface-2" />
          </div>
          <div className="h-6 w-11 shrink-0 rounded-full bg-surface-2" />
        </div>
      ))}
    </div>
  );
}

export function NotificationChannelPreferences({
  accessToken,
  helpHref,
}: NotificationChannelPreferencesProps) {
  const { t } = useLocale();
  const [preferences, setPreferences] = useState<NotificationPreferenceRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<"success" | "error" | null>(null);
  const emailRef = useRef<HTMLDivElement>(null);
  const inAppRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!accessToken) return;
    setLoading(true);
    notificationApi
      .getPreferences(accessToken)
      .then(setPreferences)
      .catch(() => setFeedback("error"))
      .finally(() => setLoading(false));
  }, [accessToken]);

  const update = async (patch: NotificationPreferenceUpdate) => {
    if (!accessToken || !preferences) return;
    setSaving(true);
    setFeedback(null);
    try {
      const updated = await notificationApi.updatePreferences(patch, accessToken);
      setPreferences(updated);
      setFeedback("success");
      window.setTimeout(() => setFeedback(null), 3000);
    } catch {
      setFeedback("error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-surface border border-border rounded-xl p-4">
      {feedback === "success" && (
        <div className="mb-3 rounded-lg border border-emerald-200 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-400">
          {t("settings.notifications.saveSuccess")}
        </div>
      )}
      {feedback === "error" && (
        <div className="mb-3 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
          {loading ? t("settings.notifications.loadError") : t("settings.notifications.saveError")}
        </div>
      )}

      {loading ? (
        <PreferenceSkeleton />
      ) : !preferences ? (
        <div className="py-6 text-center text-sm text-text-muted">
          {t("settings.notifications.loadError")}
        </div>
      ) : (
        <>
          <div ref={emailRef}>
            <InfoTooltip
              targetRef={emailRef}
              text={t("settings.notifications.emailTooltip")}
              title={t("settings.notifications.emailTitle")}
              learnMoreHref={helpHref}
            />
            <ToggleRow
              label={t("settings.notifications.emailTitle")}
              description={t("settings.notifications.emailDescription")}
              checked={preferences.email_enabled}
              saving={saving}
              onChange={(emailEnabled) => update({ email_enabled: emailEnabled })}
            />
          </div>
          <div ref={inAppRef}>
            <InfoTooltip
              targetRef={inAppRef}
              text={t("settings.notifications.inAppTooltip")}
              title={t("settings.notifications.inAppTitle")}
              learnMoreHref={helpHref}
            />
            <ToggleRow
              label={t("settings.notifications.inAppTitle")}
              description={t("settings.notifications.inAppDescription")}
              checked={preferences.in_app_enabled}
              saving={saving}
              onChange={(inAppEnabled) => update({ in_app_enabled: inAppEnabled })}
            />
          </div>
        </>
      )}
    </div>
  );
}

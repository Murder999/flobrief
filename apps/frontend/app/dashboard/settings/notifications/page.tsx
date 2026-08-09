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
    <div className="flex items-start justify-between py-5 border-b border-border last:border-b-0">
      <div className="flex-1 pr-8">
        <p className="text-sm font-medium text-text">{label}</p>
        <p className="text-xs text-text-muted mt-0.5 leading-relaxed">{description}</p>
      </div>
      <button
        role="switch"
        aria-checked={checked}
        disabled={disabled || saving}
        onClick={() => !disabled && !saving && onChange(!checked)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-surface disabled:opacity-40 flex-shrink-0 ${
          checked && !disabled ? "bg-accent" : "bg-surface-2"
        }`}
      >
        <span
          className={`inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform ${
            checked && !disabled ? "translate-x-6" : "translate-x-1"
          }`}
        />
      </button>
    </div>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function PreferenceSkeleton() {
  return (
    <div className="animate-pulse space-y-0">
      {[1, 2].map((i) => (
        <div key={i} className="flex items-start justify-between py-5 border-b border-border last:border-b-0">
          <div className="flex-1 pr-8 space-y-2">
            <div className="h-3.5 bg-surface-2 rounded w-32" />
            <div className="h-3 bg-surface-2 rounded w-64" />
          </div>
          <div className="h-6 w-11 bg-surface-2 rounded-full flex-shrink-0" />
        </div>
      ))}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function NotificationPreferencesPage() {
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();

  const [prefs, setPrefs] = useState<NotificationPreferenceRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken) return;
    notificationApi
      .getPreferences(accessToken)
      .then(setPrefs)
      .catch(() => setErrorMsg("Tercihler yüklenemedi."))
      .finally(() => setLoading(false));
  }, [accessToken]);

  const update = async (patch: NotificationPreferenceUpdate) => {
    if (!accessToken || !prefs) return;
    setSaving(true);
    setSuccessMsg(null);
    setErrorMsg(null);
    try {
      const updated = await notificationApi.updatePreferences(patch, accessToken);
      setPrefs(updated);
      setSuccessMsg("Tercihler kaydedildi.");
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch {
      setErrorMsg("Kaydedilemedi. Lütfen tekrar deneyin.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-8 max-w-2xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-text">Bildirim Tercihleri</h1>
        <p className="text-sm text-text-muted mt-1">
          Hangi kanallardan bildirim almak istediğinizi ayarlayın.
        </p>
      </div>

      {/* Feedback banners */}
      {successMsg && (
        <div className="mb-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl px-4 py-3 text-sm text-emerald-400">
          {successMsg}
        </div>
      )}
      {errorMsg && (
        <div className="mb-4 bg-danger/10 border border-danger/30 rounded-xl px-4 py-3 text-sm text-danger">
          {errorMsg}
        </div>
      )}

      {/* Email / in-app preferences card */}
      <div className="bg-surface border border-border rounded-xl px-6 mb-6">
        {loading ? (
          <PreferenceSkeleton />
        ) : !prefs ? (
          <div className="py-12 text-center text-sm text-text-muted">Tercihler yüklenemedi.</div>
        ) : (
          <>
            <ToggleRow
              label="E-posta bildirimleri"
              description="Brief onayları, revizyon istekleri ve önemli güncellemeler için e-posta alırsınız."
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
            <ToggleRow
              label="Uygulama içi bildirimler"
              description="Sidebar'daki bildirim zili ile anlık bildirimler alırsınız."
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

      {/* WhatsApp — premium preference panel (Part 6B-2) */}
      <div className="mb-2">
        <h2 className="text-sm font-semibold text-text mb-3">WhatsApp</h2>
      </div>
      <WhatsAppPreferencesPanel
        accessToken={accessToken}
        agencyId={activeAgency?.id ?? null}
        portal="agency"
        phoneSettingsHref="/dashboard/settings/profile"
      />
    </div>
  );
}

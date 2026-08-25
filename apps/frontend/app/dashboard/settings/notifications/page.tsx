"use client";

import { WhatsAppPreferencesPanel } from "@/components/notifications/WhatsAppPreferencesPanel";
import { NotificationChannelPreferences } from "@/components/notifications/NotificationChannelPreferences";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { useLocale } from "@/context/locale-context";

// ── Page ──────────────────────────────────────────────────────────────────────

export default function NotificationPreferencesPage() {
  const { t } = useLocale();
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();

  return (
    <div>
      <div className="space-y-4">
        <NotificationChannelPreferences
          accessToken={accessToken}
          helpHref="/dashboard/help?topic=notifications"
        />

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

"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import {
  whatsappPreferencesApi,
  whatsappTestSendApi,
  type WhatsAppEventPreferenceRead,
  type WhatsAppTenantTestSendResponse,
  type WhatsAppUserStatusRead,
} from "@/lib/api-client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useLocale } from "@/context/locale-context";
import type { TranslationKey } from "@/messages";

interface WhatsAppPreferencesPanelProps {
  accessToken: string | null;
  /** Agency id for agency-portal callers; null for brand-portal callers
   * (the brand-portal test-send route needs no X-Agency-ID header). */
  agencyId: string | null;
  portal: "agency" | "brand";
  phoneSettingsHref: string;
}

const GROUP_ORDER = [
  "brief_and_work",
  "comments_and_collaboration",
  "delivery_and_approval",
  "finance",
];

const GROUP_LABEL_KEYS: Record<string, TranslationKey> = {
  brief_and_work: "settings.whatsapp.group.briefAndWork",
  comments_and_collaboration: "settings.whatsapp.group.collaboration",
  delivery_and_approval: "settings.whatsapp.group.deliveryApproval",
  finance: "settings.whatsapp.group.finance",
};

const EVENT_LABEL_KEYS: Record<string, TranslationKey> = {
  "brief.created": "settings.whatsapp.event.briefCreated",
  "brief.assigned": "settings.whatsapp.event.briefAssigned",
  "comment.added": "settings.whatsapp.event.commentAdded",
  "mention.in_comment": "settings.whatsapp.event.commentMentioned",
  "mention.in_annotation": "settings.whatsapp.event.annotationMentioned",
  "deliverable.submitted": "settings.whatsapp.event.deliverableSubmitted",
  "brief.submitted_for_approval": "settings.whatsapp.event.briefSubmitted",
  "deliverable.approved": "settings.whatsapp.event.deliverableApproved",
  "brief.revision_requested": "settings.whatsapp.event.briefRevisionRequested",
  "deliverable.revision_requested": "settings.whatsapp.event.deliverableRevisionRequested",
  "annotation.created": "settings.whatsapp.event.annotationCreated",
  "annotation.replied": "settings.whatsapp.event.annotationReplied",
  "calendar.item_due": "settings.whatsapp.event.calendarDue",
  "brief.overdue": "settings.whatsapp.event.briefOverdue",
  "invoice.sent": "settings.whatsapp.event.invoiceSent",
  "invoice.due_soon": "settings.whatsapp.event.invoiceDueSoon",
  "invoice.overdue": "settings.whatsapp.event.invoiceOverdue",
  "invoice.payment_received": "settings.whatsapp.event.invoicePaymentReceived",
};

function StatusDot({ tone }: { tone: "ok" | "warn" | "off" }) {
  const cls =
    tone === "ok" ? "bg-emerald-400" : tone === "warn" ? "bg-amber-400" : "bg-text-muted/40";
  return <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${cls}`} />;
}

function Skeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="h-24 bg-surface-2 rounded-xl border border-border" />
      <div className="h-16 bg-surface-2 rounded-xl border border-border" />
      {[1, 2, 3].map((i) => (
        <div key={i} className="h-40 bg-surface-2 rounded-xl border border-border" />
      ))}
    </div>
  );
}

function Toggle({
  checked,
  disabled,
  onChange,
  label,
}: {
  checked: boolean;
  disabled?: boolean;
  onChange: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={onChange}
      className={`relative inline-flex h-6 w-11 min-w-[44px] min-h-[24px] items-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:opacity-40 flex-shrink-0 ${
        checked && !disabled ? "bg-emerald-500" : "bg-surface-2 border border-border"
      }`}
    >
      <span
        className={`inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform ${
          checked && !disabled ? "translate-x-6" : "translate-x-1"
        }`}
      />
    </button>
  );
}

export function WhatsAppPreferencesPanel({
  accessToken,
  agencyId,
  portal,
  phoneSettingsHref,
}: WhatsAppPreferencesPanelProps) {
  const { locale, t } = useLocale();
  const [status, setStatus] = useState<WhatsAppUserStatusRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [consentModalOpen, setConsentModalOpen] = useState(false);
  const [consentSubmitting, setConsentSubmitting] = useState(false);
  const [togglingEvent, setTogglingEvent] = useState<string | null>(null);
  const [testSending, setTestSending] = useState(false);
  const [testResult, setTestResult] = useState<WhatsAppTenantTestSendResponse | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!accessToken) return;
    setLoading(true);
    setLoadError(null);
    whatsappPreferencesApi
      .getStatus(agencyId, accessToken)
      .then(setStatus)
      .catch(() => setLoadError(t("settings.whatsapp.loadError")))
      .finally(() => setLoading(false));
  }, [accessToken, agencyId, t]);

  useEffect(() => {
    load();
  }, [load]);

  const handleOptIn = async () => {
    if (!accessToken) return;
    setConsentSubmitting(true);
    setActionError(null);
    try {
      const updated = await whatsappPreferencesApi.updateConsent(true, agencyId, accessToken);
      setStatus(updated);
      setConsentModalOpen(false);
    } catch {
      setActionError(t("settings.whatsapp.consentSaveError"));
    } finally {
      setConsentSubmitting(false);
    }
  };

  const handleOptOut = async () => {
    if (!accessToken) return;
    setConsentSubmitting(true);
    setActionError(null);
    try {
      const updated = await whatsappPreferencesApi.updateConsent(false, agencyId, accessToken);
      setStatus(updated);
    } catch {
      setActionError(t("settings.whatsapp.actionError"));
    } finally {
      setConsentSubmitting(false);
    }
  };

  const handleEventToggle = async (event: WhatsAppEventPreferenceRead) => {
    if (!accessToken) return;
    setTogglingEvent(event.event_type);
    setActionError(null);
    try {
      const updated = await whatsappPreferencesApi.updateEventPreference(
        event.event_type,
        !event.whatsapp_enabled,
        agencyId,
        accessToken
      );
      setStatus((prev) =>
        prev
          ? {
              ...prev,
              events: prev.events.map((e) => (e.event_type === updated.event_type ? updated : e)),
            }
          : prev
      );
    } catch {
      setActionError(t("settings.whatsapp.preferenceSaveError"));
    } finally {
      setTogglingEvent(null);
    }
  };

  const handleTestSend = async () => {
    if (!accessToken) return;
    setTestSending(true);
    setTestResult(null);
    try {
      const result =
        portal === "brand"
          ? await whatsappPreferencesApi.testSendBrand(accessToken)
          : agencyId
          ? await whatsappTestSendApi.testSend(agencyId, accessToken)
          : null;
      if (result) setTestResult(result);
      load();
    } catch (e: unknown) {
      const err = e as { message?: string };
      setTestResult({
        delivery_id: null,
        masked_recipient: null,
        status: "failed",
        provider: "unknown",
        template_key: "",
        provider_message_id: null,
        safe_error: err?.message ?? t("settings.whatsapp.testFailed"),
      });
    } finally {
      setTestSending(false);
    }
  };

  if (loading) return <Skeleton />;
  if (loadError || !status) {
    return (
      <div className="px-4 py-3 bg-danger/10 border border-danger/30 rounded-xl text-sm text-danger flex items-center justify-between gap-3">
        <span>{loadError ?? t("settings.whatsapp.loadError")}</span>
        <button onClick={load} className="text-xs underline underline-offset-2 flex-shrink-0">
          {t("settings.whatsapp.retry")}
        </button>
      </div>
    );
  }

  const { phone, consent, master_enabled, whatsapp_provider_active, events, is_demo_tenant } =
    status;

  const canOptIn = whatsapp_provider_active && phone.has_phone_number;
  const readyForTest = master_enabled && consent.whatsapp_opt_in && phone.has_phone_number;

  const groups = GROUP_ORDER.map((key) => ({
    key,
    label: GROUP_LABEL_KEYS[key] ? t(GROUP_LABEL_KEYS[key]) : events.find((e) => e.group === key)?.group_label ?? key,
    events: events.filter((e) => e.group === key),
  })).filter((g) => g.events.length > 0);

  return (
    <div className="space-y-5">
      {/* Provider not active */}
      {!whatsapp_provider_active && (
        <div className="flex gap-3 bg-surface-2 border border-border rounded-xl px-5 py-4">
          <svg className="w-4 h-4 text-text-muted flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-xs text-text-muted leading-relaxed">
            {t("settings.whatsapp.providerUnavailable")}
          </p>
        </div>
      )}

      {is_demo_tenant && (
        <div className="flex gap-3 bg-accent/5 border border-accent/20 rounded-xl px-5 py-4">
          <p className="text-xs text-text-muted leading-relaxed">
            {t("settings.whatsapp.demoNotice")}
          </p>
        </div>
      )}

      {/* Master toggle card */}
      <div className="bg-surface border border-border rounded-xl px-6 py-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-text">{t("settings.whatsapp.title")}</h3>
              <Badge variant={master_enabled ? "success" : "default"}>
                {master_enabled ? t("settings.whatsapp.on") : t("settings.whatsapp.off")}
              </Badge>
            </div>
            <p className="text-xs text-text-muted mt-1 leading-relaxed max-w-md">
              {t("settings.whatsapp.masterDescription")}
            </p>
          </div>
          <Toggle
            checked={master_enabled}
            disabled={!canOptIn && !master_enabled}
            label={t("settings.whatsapp.toggleLabel")}
            onChange={() => (master_enabled ? handleOptOut() : setConsentModalOpen(true))}
          />
        </div>

        <div className="mt-4 pt-4 border-t border-border grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="flex items-center gap-2 text-xs">
            <StatusDot tone={phone.has_phone_number ? "ok" : "warn"} />
            <span className="text-text-muted">{t("settings.whatsapp.phoneStatus")}</span>
            {phone.has_phone_number ? (
              <span className="font-mono text-text">{phone.phone_masked}</span>
            ) : (
              <Link href={phoneSettingsHref} className="text-accent hover:underline">
                {t("settings.whatsapp.addPhone")}
              </Link>
            )}
            {phone.has_phone_number && !phone.phone_verified && (
              <span className="text-text-muted/70">({t("settings.whatsapp.unverified")})</span>
            )}
          </div>
          <div className="flex items-center gap-2 text-xs">
            <StatusDot tone={consent.whatsapp_opt_in ? "ok" : "off"} />
            <span className="text-text-muted">{t("settings.whatsapp.consentStatus")}</span>
            <span className="text-text">
              {consent.whatsapp_opt_in && consent.whatsapp_opt_in_at
                ? `${t("settings.whatsapp.consentGiven")} — ${new Date(consent.whatsapp_opt_in_at).toLocaleDateString(locale === "tr" ? "tr-TR" : "en-US")}`
                : consent.whatsapp_opt_out_at
                ? `${t("settings.whatsapp.consentWithdrawn")} — ${new Date(consent.whatsapp_opt_out_at).toLocaleDateString(locale === "tr" ? "tr-TR" : "en-US")}`
                : t("settings.whatsapp.consentMissing")}
            </span>
          </div>
        </div>
      </div>

      {actionError && (
        <div className="px-4 py-2.5 bg-danger/10 border border-danger/30 rounded-lg text-xs text-danger">
          {actionError}
        </div>
      )}

      {/* Event groups */}
      {master_enabled && groups.length > 0 && (
        <div className="space-y-4">
          {groups.map((group) => (
            <div key={group.key} className="bg-surface border border-border rounded-xl overflow-hidden">
              <div className="px-5 py-3 bg-surface-2/50 border-b border-border">
                <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wide">
                  {group.label}
                </h4>
              </div>
              <div className="divide-y divide-border">
                {group.events.map((event) => (
                  <div
                    key={event.event_type}
                    className="flex items-center justify-between gap-4 px-5 py-3.5"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-text truncate">
                        {EVENT_LABEL_KEYS[event.event_type] ? t(EVENT_LABEL_KEYS[event.event_type]) : event.event_label}
                      </p>
                      {!event.template_ready && (
                        <p className="text-[11px] text-amber-400 mt-0.5">
                          {t("settings.whatsapp.templatePending")}
                        </p>
                      )}
                    </div>
                    <Toggle
                      checked={event.whatsapp_enabled}
                      disabled={togglingEvent === event.event_type}
                      label={EVENT_LABEL_KEYS[event.event_type] ? t(EVENT_LABEL_KEYS[event.event_type]) : event.event_label}
                      onChange={() => handleEventToggle(event)}
                    />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Test send + last delivery */}
      <div className="bg-surface border border-border rounded-xl px-5 py-4">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <p className="text-sm font-medium text-text">{t("settings.whatsapp.testTitle")}</p>
            <p className="text-xs text-text-muted mt-0.5">
              {t("settings.whatsapp.testDescription")}
            </p>
          </div>
          <Button
            variant="secondary"
            size="sm"
            disabled={testSending || !readyForTest}
            onClick={handleTestSend}
          >
            {testSending ? t("settings.whatsapp.testSending") : t("settings.whatsapp.testSend")}
          </Button>
        </div>
        {!readyForTest && (
          <p className="text-xs text-text-muted mt-2">
            {t("settings.whatsapp.testRequirements")}
          </p>
        )}
        {testResult && (
          <div className="mt-3 p-3 bg-surface-2 border border-border rounded-lg text-xs space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="text-text-muted w-20">{t("settings.whatsapp.resultStatus")}</span>
              <code className="font-mono px-2 py-0.5 rounded border bg-surface text-text border-border">
                {testResult.status}
              </code>
            </div>
            {testResult.masked_recipient && (
              <div className="flex items-center gap-2">
                <span className="text-text-muted w-20">{t("settings.whatsapp.resultRecipient")}</span>
                <code className="font-mono text-text">{testResult.masked_recipient}</code>
              </div>
            )}
            {testResult.safe_error && (
              <div className="flex items-start gap-2">
                <span className="text-text-muted w-20 flex-shrink-0">{t("settings.whatsapp.resultNote")}</span>
                <span className="text-text-muted">{testResult.safe_error}</span>
              </div>
            )}
          </div>
        )}
        {status.last_delivery_status && (
          <p className="mt-3 text-[11px] text-text-muted">
            {t("settings.whatsapp.lastDelivery")}: <span className="font-mono">{status.last_delivery_status}</span>
            {status.last_delivery_at &&
              ` — ${new Date(status.last_delivery_at).toLocaleString(locale === "tr" ? "tr-TR" : "en-US")}`}
          </p>
        )}
      </div>

      <Modal
        isOpen={consentModalOpen}
        onClose={() => setConsentModalOpen(false)}
        title={t("settings.whatsapp.consentTitle")}
        maxWidth="sm"
      >
        <div className="space-y-4">
          <p className="text-sm text-text-secondary leading-relaxed">
            {t("settings.whatsapp.consentBody")}
          </p>
          <ul className="text-xs text-text-muted space-y-1.5 list-disc list-inside">
            <li>{t("settings.whatsapp.consentBulletControl")}</li>
            <li>{t("settings.whatsapp.consentBulletPrivacy")}</li>
            <li>{t("settings.whatsapp.consentBulletDemo")}</li>
          </ul>
          {actionError && <p className="text-xs text-danger">{actionError}</p>}
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="ghost" size="sm" onClick={() => setConsentModalOpen(false)}>
              {t("settings.whatsapp.cancel")}
            </Button>
            <Button variant="primary" size="sm" isLoading={consentSubmitting} onClick={handleOptIn}>
              {t("settings.whatsapp.confirm")}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

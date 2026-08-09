"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import {
  whatsappAdminApi,
  whatsappPreferencesApi,
  whatsappTestSendApi,
  type WhatsAppAgencySummaryRead,
  type WhatsAppDeliveryHistoryItemRead,
  type WhatsAppTemplateMatrixRowRead,
  type WhatsAppTemplatePreviewRead,
  type WhatsAppTenantTestSendResponse,
  type WhatsAppUserStatusRead,
} from "@/lib/api-client";
import { useCallback, useEffect, useState } from "react";

const CONNECTION_LABELS: Record<string, string> = {
  disabled: "Devre Dışı",
  not_configured: "Yapılandırılmamış",
  sandbox: "Sandbox",
  connected: "Bağlı",
  degraded: "Kısmi Sorunlu",
  error: "Hata",
};

function ConnectionBadge({ status }: { status: string }) {
  const variant =
    status === "connected" ? "success" : status === "error" ? "danger" : status === "degraded" ? "warning" : "default";
  return <Badge variant={variant}>{CONNECTION_LABELS[status] ?? status}</Badge>;
}

function StatCard({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="bg-surface border border-border rounded-xl px-4 py-3.5">
      <p className="text-[11px] font-medium text-text-muted uppercase tracking-wide">{label}</p>
      <p className="text-xl font-semibold text-text mt-1">{value}</p>
      {hint && <p className="text-[11px] text-text-muted mt-0.5">{hint}</p>}
    </div>
  );
}

function DeliverySummaryRow({ counts, title }: { counts: Record<string, number>; title: string }) {
  const entries = Object.entries(counts).filter(([, v]) => v > 0);
  return (
    <div className="bg-surface border border-border rounded-xl px-4 py-3.5">
      <p className="text-[11px] font-medium text-text-muted uppercase tracking-wide mb-2">{title}</p>
      {entries.length === 0 ? (
        <p className="text-xs text-text-muted">Kayıt yok</p>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {entries.map(([status, count]) => (
            <span
              key={status}
              className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-mono bg-surface-2 border border-border text-text"
            >
              {status}: {count}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

const STATUS_BADGE: Record<string, "success" | "warning" | "danger" | "default"> = {
  approved: "success",
  draft: "default",
  pending: "warning",
  rejected: "danger",
  disabled: "danger",
};

function TemplateMatrixCard({ row, onPreview }: { row: WhatsAppTemplateMatrixRowRead; onPreview: () => void }) {
  return (
    <div className="bg-surface border border-border rounded-xl p-4 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-text">{row.event_label}</p>
        <Badge variant={STATUS_BADGE[row.status] ?? "default"}>{row.status}</Badge>
      </div>
      <p className="text-[11px] font-mono text-text-muted">{row.template_key} · {row.locale}</p>
      <div className="flex items-center gap-3 text-[11px] text-text-muted">
        <span>{row.has_content_sid ? "Content SID mevcut" : "Content SID yok"}</span>
        <span>·</span>
        <span>{row.approved_at ? new Date(row.approved_at).toLocaleDateString("tr-TR") : "Onaylanmadı"}</span>
      </div>
      <p className="text-[11px] text-text-muted leading-relaxed">{row.recipient_policy}</p>
      <button onClick={onPreview} className="text-xs text-accent hover:underline">
        Önizle →
      </button>
    </div>
  );
}

function DeliveryCard({ item }: { item: WhatsAppDeliveryHistoryItemRead }) {
  return (
    <div className="bg-surface border border-border rounded-xl p-4 space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm text-text font-medium">{item.event_type}</p>
        <Badge variant={item.status === "sent" || item.status === "delivered" || item.status === "read" ? "success" : item.status.startsWith("skipped") ? "default" : item.status === "failed" ? "danger" : "warning"}>
          {item.status}
        </Badge>
      </div>
      <p className="text-[11px] text-text-muted">
        {new Date(item.created_at).toLocaleString("tr-TR")}
      </p>
      <div className="flex items-center gap-2 text-[11px] text-text-muted flex-wrap">
        {item.recipient_display_name && <span>{item.recipient_display_name}</span>}
        {item.recipient_phone_masked && <span className="font-mono">{item.recipient_phone_masked}</span>}
        {item.template_key && <span className="font-mono">{item.template_key}</span>}
      </div>
      {item.safe_error && <p className="text-[11px] text-danger">{item.safe_error}</p>}
    </div>
  );
}

export function WhatsAppOwnerCenter() {
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();
  const agencyId = activeAgency?.id ?? null;

  const [status, setStatus] = useState<WhatsAppUserStatusRead | null>(null);
  const [summary, setSummary] = useState<WhatsAppAgencySummaryRead | null>(null);
  const [matrix, setMatrix] = useState<WhatsAppTemplateMatrixRowRead[]>([]);
  const [deliveries, setDeliveries] = useState<WhatsAppDeliveryHistoryItemRead[]>([]);
  const [deliveryTotal, setDeliveryTotal] = useState(0);
  const [deliveryOffset, setDeliveryOffset] = useState(0);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [testSending, setTestSending] = useState(false);
  const [testResult, setTestResult] = useState<WhatsAppTenantTestSendResponse | null>(null);
  const [previewEvent, setPreviewEvent] = useState<WhatsAppTemplatePreviewRead | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const PAGE_SIZE = 10;

  const loadCore = useCallback(async () => {
    if (!accessToken || !agencyId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const [statusRes, summaryRes, matrixRes] = await Promise.all([
        whatsappPreferencesApi.getStatus(agencyId, accessToken),
        whatsappAdminApi.getSummary(agencyId, accessToken),
        whatsappAdminApi.getTemplateMatrix(agencyId, accessToken),
      ]);
      setStatus(statusRes);
      setSummary(summaryRes);
      setMatrix(matrixRes);
    } catch {
      setLoadError("WhatsApp merkezi yüklenemedi.");
    } finally {
      setLoading(false);
    }
  }, [accessToken, agencyId]);

  const loadDeliveries = useCallback(
    async (offset: number, status_filter: string) => {
      if (!accessToken || !agencyId) return;
      try {
        const page = await whatsappAdminApi.listDeliveries(agencyId, accessToken, {
          limit: PAGE_SIZE,
          offset,
          status: status_filter || undefined,
        });
        setDeliveries(page.items);
        setDeliveryTotal(page.total);
        setDeliveryOffset(offset);
      } catch {
        // Delivery history failing to load shouldn't block the rest of the center.
      }
    },
    [accessToken, agencyId]
  );

  useEffect(() => {
    loadCore();
  }, [loadCore]);

  useEffect(() => {
    loadDeliveries(0, statusFilter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, agencyId]);

  const handleTestSend = async () => {
    if (!accessToken || !agencyId) return;
    setTestSending(true);
    setTestResult(null);
    try {
      const result = await whatsappTestSendApi.testSend(agencyId, accessToken);
      setTestResult(result);
      loadCore();
      loadDeliveries(0, statusFilter);
    } catch (e: unknown) {
      const err = e as { message?: string };
      setTestResult({
        delivery_id: null,
        masked_recipient: null,
        status: "failed",
        provider: "unknown",
        template_key: "flobrief_test_notification",
        provider_message_id: null,
        safe_error: err?.message ?? "Test bildirimi gönderilemedi.",
      });
    } finally {
      setTestSending(false);
    }
  };

  const handlePreview = async (eventType: string) => {
    if (!accessToken || !agencyId) return;
    setPreviewLoading(true);
    try {
      const preview = await whatsappAdminApi.getTemplatePreview(eventType, agencyId, accessToken);
      setPreviewEvent(preview);
    } catch {
      // silent — preview is a nice-to-have, not blocking
    } finally {
      setPreviewLoading(false);
    }
  };

  const readyForTest =
    (status?.whatsapp_provider_active ?? false) &&
    (status?.phone.has_phone_number ?? false) &&
    (status?.consent.whatsapp_opt_in ?? false);

  if (loading) {
    return (
      <div className="space-y-5 animate-pulse">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-20 bg-surface-2 rounded-xl border border-border" />
          ))}
        </div>
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-40 bg-surface-2 rounded-xl border border-border" />
        ))}
      </div>
    );
  }

  if (loadError || !summary) {
    return (
      <div className="px-4 py-3 bg-danger/10 border border-danger/30 rounded-xl text-sm text-danger flex items-center justify-between gap-3">
        <span>{loadError ?? "WhatsApp merkezi yüklenemedi."}</span>
        <button onClick={loadCore} className="text-xs underline underline-offset-2 flex-shrink-0">
          Tekrar dene
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {summary.demo_tenant && (
        <div className="px-4 py-3 bg-accent/5 border border-accent/20 rounded-xl text-xs text-text-muted">
          Demo ortamda gerçek WhatsApp gönderimi yapılmaz — aşağıdaki veriler simülasyon amaçlıdır.
        </div>
      )}

      {/* Connection + stats */}
      <div className="bg-surface border border-border rounded-xl px-5 py-4">
        <div className="flex items-center gap-3 flex-wrap">
          <ConnectionBadge status={summary.connection_status} />
          <span className="text-sm text-text-muted">
            {summary.sender_masked ? `Gönderen: ${summary.sender_masked}` : "Gönderen yapılandırılmamış"}
          </span>
          <span className="text-xs text-text-muted/70">· {summary.environment}</span>
        </div>
        {summary.last_safe_error && (
          <p className="text-xs text-danger mt-2">Son hata: {summary.last_safe_error}</p>
        )}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard label="Opt-in kullanıcı" value={summary.opted_in_users} />
        <StatCard label="WhatsApp aktif kullanıcı" value={summary.whatsapp_enabled_users} />
        <StatCard label="Hazır şablon" value={summary.templates_ready} />
        <StatCard label="Eksik/taslak şablon" value={summary.templates_not_ready} />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard label="Retry kuyruğu" value={summary.retry_queue} />
        <StatCard label="Retry tükendi" value={summary.retry_exhausted} />
        <StatCard
          label="Gönderim başarı oranı (7g)"
          value={summary.delivery_success_rate_7d != null ? `%${Math.round(summary.delivery_success_rate_7d * 100)}` : "—"}
        />
        <StatCard
          label="Okunma oranı (7g)"
          value={summary.read_rate_7d != null ? `%${Math.round(summary.read_rate_7d * 100)}` : "—"}
          hint={summary.top_failure_category_7d ? `En sık hata: ${summary.top_failure_category_7d}` : undefined}
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <DeliverySummaryRow counts={summary.deliveries_24h} title="Son 24 saat" />
        <DeliverySummaryRow counts={summary.deliveries_7d} title="Son 7 gün" />
      </div>

      {/* Test send */}
      <div className="bg-surface border border-border rounded-xl px-5 py-4">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <p className="text-sm font-medium text-text">Test mesajı gönder</p>
            <p className="text-xs text-text-muted mt-0.5">Kendi kayıtlı numaranıza kontrollü bir test mesajı gönderir.</p>
          </div>
          <Button variant="secondary" size="sm" disabled={testSending || !readyForTest} onClick={handleTestSend}>
            {testSending ? "Gönderiliyor…" : "Test Mesajı Gönder"}
          </Button>
        </div>
        {testResult && (
          <div className="mt-3 p-3 bg-surface-2 border border-border rounded-lg text-xs space-y-1">
            <div>Durum: <code className="font-mono">{testResult.status}</code></div>
            {testResult.safe_error && <div className="text-text-muted">{testResult.safe_error}</div>}
          </div>
        )}
      </div>

      {/* Template matrix */}
      <div>
        <h3 className="text-sm font-semibold text-text mb-3">Event–Şablon Matrisi</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {matrix.map((row) => (
            <TemplateMatrixCard key={row.event_type} row={row} onPreview={() => handlePreview(row.event_type)} />
          ))}
        </div>
      </div>

      {/* Delivery history */}
      <div>
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <h3 className="text-sm font-semibold text-text">Teslimat Geçmişi</h3>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-surface-2 border border-border rounded-lg px-3 py-1.5 text-xs text-text focus:outline-none focus:border-accent/50"
          >
            <option value="">Tüm durumlar</option>
            <option value="sent">sent</option>
            <option value="delivered">delivered</option>
            <option value="read">read</option>
            <option value="failed">failed</option>
            <option value="cancelled">cancelled</option>
            <option value="expired">expired</option>
            <option value="skipped_no_consent">skipped_no_consent</option>
            <option value="skipped_template_missing">skipped_template_missing</option>
            <option value="skipped_event_disabled">skipped_event_disabled</option>
            <option value="skipped_demo_tenant">skipped_demo_tenant</option>
            <option value="skipped_role">skipped_role</option>
          </select>
        </div>
        {deliveries.length === 0 ? (
          <div className="bg-surface border border-border rounded-xl px-5 py-10 text-center text-sm text-text-muted">
            Henüz teslimat kaydı yok.
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {deliveries.map((item) => (
              <DeliveryCard key={item.id} item={item} />
            ))}
          </div>
        )}
        {deliveryTotal > PAGE_SIZE && (
          <div className="flex items-center justify-between mt-3 text-xs text-text-muted">
            <span>
              {deliveryOffset + 1}-{Math.min(deliveryOffset + PAGE_SIZE, deliveryTotal)} / {deliveryTotal}
            </span>
            <div className="flex gap-2">
              <button
                disabled={deliveryOffset === 0}
                onClick={() => loadDeliveries(Math.max(0, deliveryOffset - PAGE_SIZE), statusFilter)}
                className="px-2.5 py-1 rounded-md border border-border disabled:opacity-40"
              >
                Önceki
              </button>
              <button
                disabled={deliveryOffset + PAGE_SIZE >= deliveryTotal}
                onClick={() => loadDeliveries(deliveryOffset + PAGE_SIZE, statusFilter)}
                className="px-2.5 py-1 rounded-md border border-border disabled:opacity-40"
              >
                Sonraki
              </button>
            </div>
          </div>
        )}
      </div>

      <Modal
        isOpen={previewEvent !== null || previewLoading}
        onClose={() => setPreviewEvent(null)}
        title={previewEvent?.event_label ?? "Şablon Önizleme"}
        maxWidth="md"
      >
        {previewEvent && (
          <div className="space-y-3">
            <div className="bg-surface-2 border border-border rounded-lg px-4 py-3 text-sm text-text">
              {previewEvent.sample_message}
            </div>
            <div className="text-xs text-text-muted space-y-1">
              <p>Şablon: <span className="font-mono">{previewEvent.template_key}</span> · {previewEvent.locale}</p>
              <p>Alıcı rolü: {previewEvent.recipient_roles}</p>
              <p>Değişkenler: {previewEvent.variable_names.join(", ")}</p>
            </div>
            <p className="text-[11px] text-text-muted/70 italic">{previewEvent.sensitive_data_note}</p>
          </div>
        )}
      </Modal>
    </div>
  );
}

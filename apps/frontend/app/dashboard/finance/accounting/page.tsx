"use client";

import { ConnectorConfigForm } from "@/components/finance/ConnectorConfigForm";
import { ConnectorStatusBadge } from "@/components/finance/ConnectorStatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { SkeletonCard } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { ApiError, financeApi, type AccountingConnectorRead } from "@/lib/api-client";
import { ACCOUNTING_PROVIDER_LABEL, canManageConnectors, formatDate } from "@/lib/finance";
import { Lock, Pencil, Plug, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.detail === "string") return e.detail;
    return e.message;
  }
  return e instanceof Error ? e.message : "İşlem başarısız";
}

function fmtDateTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("tr-TR", { dateStyle: "medium", timeStyle: "short" });
}

/** Accounting connector settings — Phase 5 of the resource/finance plan
 * (plan §14). `ACCOUNTING_INTEGRATION_MANAGE` is Owner-only per plan §8 —
 * the fetch itself (not just the render) is gated behind
 * `canManageConnectors`, matching `FinanceSettingsPage`'s cost-rate
 * convention: a non-Owner session never issues the request at all. Only
 * `provider: "manual"` is ever real; every other value is disabled in the
 * config form's dropdown (plan §10/§12) — this page never implies a
 * quickbooks/xero/etc. connection is live. */
export default function AccountingConnectorsPage() {
  const { accessToken } = useAuth();
  const { activeAgency, isInitialized } = useWorkspace();
  const { toast, confirm } = useToast();
  const agencyId = activeAgency?.id ?? null;
  const role = activeAgency?.member_role ?? null;
  const canManage = canManageConnectors(role);

  const [connectors, setConnectors] = useState<AccountingConnectorRead[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<AccountingConnectorRead | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!accessToken || !agencyId || !canManage) return;
    setLoading(true);
    setError(null);
    try {
      const data = await financeApi.listConnectors(agencyId, accessToken);
      setConnectors(data);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [accessToken, agencyId, canManage]);

  useEffect(() => {
    load();
  }, [load]);

  const openCreate = () => {
    setEditing(null);
    setFormOpen(true);
  };

  const openEdit = (connector: AccountingConnectorRead) => {
    setEditing(connector);
    setFormOpen(true);
  };

  const handleTest = async (connector: AccountingConnectorRead) => {
    if (!accessToken || !agencyId) return;
    setTestingId(connector.id);
    try {
      const result = await financeApi.testConnectorConnection(connector.id, agencyId, accessToken);
      toast(
        result.connected ? "Bağlantı testi başarılı." : "Bağlantı testi başarısız oldu.",
        result.connected ? "success" : "error"
      );
      load();
    } catch (e) {
      toast(errorMessage(e), "error");
    } finally {
      setTestingId(null);
    }
  };

  const handleDelete = async (connector: AccountingConnectorRead) => {
    if (!accessToken || !agencyId) return;
    const ok = await confirm({
      title: "Bağlantıyı Sil",
      message: `"${ACCOUNTING_PROVIDER_LABEL[connector.provider]}" bağlantısını silmek istediğinize emin misiniz?`,
      confirmLabel: "Sil",
      destructive: true,
    });
    if (!ok) return;
    setDeletingId(connector.id);
    try {
      await financeApi.deleteConnector(connector.id, agencyId, accessToken);
      toast("Bağlantı silindi.", "success");
      load();
    } catch (e) {
      toast(errorMessage(e), "error");
    } finally {
      setDeletingId(null);
    }
  };

  if (!isInitialized || !agencyId || !accessToken) return null;

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold text-text">Muhasebe Entegrasyonu</h1>
          <p className="text-sm text-text-muted mt-1">
            Fatura verilerini bir muhasebe sistemine bağlayın. Şu an yalnızca &ldquo;Manuel&rdquo;
            bağlantı tipi çalışır — diğer sağlayıcılar yakında eklenecek.
          </p>
        </div>
        {canManage && connectors && connectors.length > 0 && (
          <Button size="sm" onClick={openCreate}>
            <Plus className="w-3.5 h-3.5" />
            Bağlantı Ekle
          </Button>
        )}
      </div>

      {!canManage ? (
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-sm text-text-muted">
              <Lock className="w-4 h-4 flex-shrink-0" />
              Bu sayfayı görüntüleme yetkiniz yok — yalnızca ajans sahibi muhasebe
              entegrasyonlarını yönetebilir.
            </div>
          </CardContent>
        </Card>
      ) : error ? (
        <div className="bg-danger/10 border border-danger/30 rounded-xl p-4 text-sm text-danger">
          {error}
        </div>
      ) : loading ? (
        <div className="space-y-3">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : !connectors || connectors.length === 0 ? (
        <Card>
          <CardContent className="pt-10 pb-10 flex flex-col items-center text-center">
            <div className="w-14 h-14 bg-surface-2 rounded-2xl flex items-center justify-center mb-4">
              <Plug className="w-6 h-6 text-text-muted" />
            </div>
            <p className="text-sm font-medium text-text mb-1">
              Henüz bir muhasebe bağlantısı yapılandırılmadı
            </p>
            <p className="text-xs text-text-muted max-w-sm mb-5">
              Faturalarınızı bir muhasebe sistemiyle eşlemek için bir bağlantı ekleyin. Bugün
              yalnızca &ldquo;Manuel&rdquo; bağlantı tipi gerçek işlevsellik sunar.
            </p>
            <Button size="sm" onClick={openCreate}>
              <Plus className="w-3.5 h-3.5" />
              Bağlantı Ekle
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {connectors.map((connector) => (
            <Card key={connector.id}>
              <CardContent className="pt-6">
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-sm font-semibold text-text">
                        {ACCOUNTING_PROVIDER_LABEL[connector.provider] ?? connector.provider}
                      </p>
                      <ConnectorStatusBadge status={connector.status} />
                    </div>
                    <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 text-xs text-text-muted">
                      <span>Son test: {fmtDateTime(connector.last_tested_at)}</span>
                      <span>Son senkronizasyon: {fmtDateTime(connector.last_sync_at)}</span>
                      <span>Eklenme: {formatDate(connector.created_at)}</span>
                    </div>
                    {connector.last_error && (
                      <p className="mt-2 text-xs text-danger bg-danger/10 border border-danger/20 rounded-lg px-2.5 py-1.5 max-w-md">
                        {connector.last_error}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => handleTest(connector)}
                      isLoading={testingId === connector.id}
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                      Bağlantıyı Test Et
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => openEdit(connector)}>
                      <Pencil className="w-3.5 h-3.5" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleDelete(connector)}
                      isLoading={deletingId === connector.id}
                    >
                      <Trash2 className="w-3.5 h-3.5 text-danger" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {canManage && (
        <ConnectorConfigForm
          isOpen={formOpen}
          onClose={() => setFormOpen(false)}
          agencyId={agencyId}
          accessToken={accessToken}
          connector={editing}
          onSaved={() => load()}
        />
      )}
    </div>
  );
}

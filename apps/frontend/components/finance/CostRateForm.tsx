"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable, type DataTableColumn } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import {
  ApiError,
  financeApi,
  type AgencyMemberRead,
  type MemberCostRateCreatePayload,
  type MemberCostRateRead,
} from "@/lib/api-client";
import { COST_RATE_ROLE_OPTIONS, FINANCE_CURRENCIES, formatDate, formatMoneyCents } from "@/lib/finance";
import { ROLE_LABELS } from "@/lib/workspace";
import { ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

interface CostRateFormProps {
  agencyId: string;
  accessToken: string;
  members: AgencyMemberRead[];
}

type TargetType = "user" | "role";

function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.detail === "string") return e.detail;
    return e.message;
  }
  return e instanceof Error ? e.message : "İşlem başarısız";
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Owner-only cost-rate management. The caller (finance settings page) must
 * never mount this component for a non-Owner viewer — it fetches
 * `MemberCostRate` rows the instant it mounts, and even a 403 response
 * would be an information leak about numeric cost data existing at all.
 * This component performs no role check of its own; visibility is the
 * caller's responsibility by design (single source of truth for the gate,
 * see `apps/frontend/app/dashboard/finance/settings/page.tsx`). */
export function CostRateForm({ agencyId, accessToken, members }: CostRateFormProps) {
  const { toast } = useToast();
  const [targetType, setTargetType] = useState<TargetType>("user");
  const [targetUserId, setTargetUserId] = useState<string>(members[0]?.user_id ?? "");
  const [targetRole, setTargetRole] = useState<string>(COST_RATE_ROLE_OPTIONS[0]);

  const [rates, setRates] = useState<MemberCostRateRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [currency, setCurrency] = useState("TRY");
  const [hourlyCost, setHourlyCost] = useState("");
  const [validFrom, setValidFrom] = useState(todayIso());
  const [validUntil, setValidUntil] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (targetType === "user" && !targetUserId) {
      setRates([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const target = targetType === "user" ? { userId: targetUserId } : { role: targetRole };
      const items = await financeApi.listCostRates(target, agencyId, accessToken);
      setRates(items);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [targetType, targetUserId, targetRole, agencyId, accessToken]);

  useEffect(() => {
    load();
  }, [load]);

  const activeRate = rates.find((r) => r.active) ?? null;

  const handleCreate = async () => {
    setFormError(null);
    const cents = Math.round(Number(hourlyCost) * 100);
    if (!Number.isFinite(cents) || cents <= 0) {
      setFormError("Saatlik maliyet pozitif bir sayı olmalı");
      return;
    }
    setSaving(true);
    try {
      const payload: MemberCostRateCreatePayload = {
        user_id: targetType === "user" ? targetUserId : null,
        role: targetType === "role" ? targetRole : null,
        currency,
        hourly_cost_cents: cents,
        valid_from: validFrom,
        valid_until: validUntil.trim() || null,
      };
      await financeApi.createCostRate(payload, agencyId, accessToken);
      toast(activeRate ? "Maliyet oranı güncellendi (önceki oran kapatıldı)." : "Maliyet oranı eklendi.", "success");
      setHourlyCost("");
      setValidUntil("");
      await load();
    } catch (e) {
      const message = errorMessage(e);
      setFormError(message);
      toast(message, "error");
    } finally {
      setSaving(false);
    }
  };

  const columns: DataTableColumn<MemberCostRateRead>[] = [
    {
      key: "hourly_cost_cents",
      header: "Saatlik Maliyet",
      render: (r) => formatMoneyCents(r.hourly_cost_cents, r.currency),
      align: "right",
    },
    { key: "valid_from", header: "Başlangıç", render: (r) => formatDate(r.valid_from) },
    { key: "valid_until", header: "Bitiş", render: (r) => formatDate(r.valid_until) },
    {
      key: "active",
      header: "Durum",
      render: (r) => (
        <Badge variant={r.active ? "success" : "default"}>{r.active ? "Aktif" : "Kapalı"}</Badge>
      ),
      align: "center",
    },
  ];

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-warning" />
            Maliyet Oranları
          </CardTitle>
          <CardDescription>
            Ekip üyesi veya rol bazında iç saatlik maliyet — yalnızca Owner rolü görebilir, kârlılık
            hesaplarında kullanılır.
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-5">
          <Select
            label="Hedef Türü"
            value={targetType}
            onChange={(e) => setTargetType(e.target.value as TargetType)}
            options={[
              { value: "user", label: "Belirli Kullanıcı" },
              { value: "role", label: "Rol (Varsayılan)" },
            ]}
          />
          {targetType === "user" ? (
            <Select
              label="Kullanıcı"
              value={targetUserId}
              onChange={(e) => setTargetUserId(e.target.value)}
              options={members.map((m) => ({
                value: m.user_id,
                label: m.user_full_name ?? m.user_email ?? m.user_id,
              }))}
            />
          ) : (
            <Select
              label="Rol"
              value={targetRole}
              onChange={(e) => setTargetRole(e.target.value)}
              options={COST_RATE_ROLE_OPTIONS.map((r) => ({ value: r, label: ROLE_LABELS[r] ?? r }))}
            />
          )}
        </div>

        {loading ? (
          <div className="h-32 bg-surface-2 rounded-xl animate-pulse" />
        ) : error ? (
          <p className="text-sm text-danger">{error}</p>
        ) : (
          <DataTable
            columns={columns}
            data={rates}
            rowKey={(r) => r.id}
            emptyMessage="Bu hedef için henüz maliyet oranı tanımlanmamış"
          />
        )}

        <div className="mt-6 pt-5 border-t border-border">
          <p className="text-xs font-medium text-text-muted mb-3 tracking-wide">
            {activeRate ? "Yeni Oran Tanımla (Aktif Oranı Kapatır)" : "Oran Ekle"}
          </p>
          {formError && <p className="text-sm text-danger mb-3">{formError}</p>}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 items-end">
            <Select
              label="Para Birimi"
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              options={FINANCE_CURRENCIES.map((c) => ({ value: c, label: c }))}
            />
            <Input
              label={`Saatlik Maliyet (${currency})`}
              type="number"
              min={0}
              step="0.01"
              value={hourlyCost}
              onChange={(e) => setHourlyCost(e.target.value)}
            />
            <Input
              label="Başlangıç"
              type="date"
              value={validFrom}
              onChange={(e) => setValidFrom(e.target.value)}
            />
            <Input
              label="Bitiş (opsiyonel)"
              type="date"
              value={validUntil}
              onChange={(e) => setValidUntil(e.target.value)}
            />
          </div>
          <div className="flex justify-end mt-4">
            <Button
              size="sm"
              onClick={handleCreate}
              isLoading={saving}
              disabled={targetType === "user" && !targetUserId}
            >
              Kaydet
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

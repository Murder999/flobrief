"use client";

import { BillableTimeTable } from "@/components/finance/BillableTimeTable";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { DateRangeFilter } from "@/components/time-tracking/DateRangeFilter";
import { TIME_CATEGORY_OPTIONS } from "@/components/time-tracking/TimeCategoryBadge";
import { useDateRangeFilter } from "@/hooks/useDateRangeFilter";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import {
  agencyApi,
  briefApi,
  financeApi,
  ApiError,
  type AgencyMemberRead,
  type BillableTimeEntryRead,
  type BrandRead,
  type TimeEntryCategory,
} from "@/lib/api-client";
import { canManageInvoices } from "@/lib/finance";
import { Building2, FileText } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

export default function BillableTimePage() {
  const { accessToken } = useAuth();
  const { activeAgency, isInitialized } = useWorkspace();
  const { toast } = useToast();
  const router = useRouter();
  const agencyId = activeAgency?.id ?? null;
  const role = activeAgency?.member_role ?? null;
  const canCreateDraft = canManageInvoices(role);
  const dateRange = useDateRangeFilter();

  const [brands, setBrands] = useState<BrandRead[]>([]);
  const [brandId, setBrandId] = useState<string>("");
  const [brandsLoading, setBrandsLoading] = useState(true);
  const [brandsError, setBrandsError] = useState<string | null>(null);

  const [members, setMembers] = useState<AgencyMemberRead[]>([]);
  const [briefTitles, setBriefTitles] = useState<Record<string, string>>({});

  const [entries, setEntries] = useState<BillableTimeEntryRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [userFilter, setUserFilter] = useState<string>("");
  const [categoryFilter, setCategoryFilter] = useState<string>("");

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [creatingDraft, setCreatingDraft] = useState(false);

  useEffect(() => {
    if (!accessToken || !agencyId) return;
    setBrandsLoading(true);
    setBrandsError(null);
    agencyApi
      .listBrands(agencyId, accessToken)
      .then((list) => {
        setBrands(list);
        setBrandId((prev) => prev || list[0]?.id || "");
      })
      .catch((e) => setBrandsError(e instanceof Error ? e.message : "Markalar yüklenemedi"))
      .finally(() => setBrandsLoading(false));
  }, [accessToken, agencyId]);

  useEffect(() => {
    if (!accessToken || !agencyId) return;
    agencyApi
      .listMembers(agencyId, accessToken)
      .then((mems) => setMembers(mems.filter((m) => m.status === "active")))
      .catch(() => {
        /* non-fatal: table falls back to showing raw user ids */
      });
  }, [accessToken, agencyId]);

  const memberNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const m of members) map[m.user_id] = m.user_full_name ?? m.user_email ?? m.user_id;
    return map;
  }, [members]);

  const load = useCallback(async () => {
    if (!accessToken || !agencyId || !brandId) return;
    setLoading(true);
    setError(null);
    setSelected(new Set());
    try {
      const start = dateRange.start ? `${dateRange.start}T00:00:00` : undefined;
      const end = dateRange.end ? `${dateRange.end}T23:59:59` : undefined;
      const [data, briefs] = await Promise.all([
        financeApi.listBillableTime(brandId, agencyId, accessToken, { start, end }),
        briefApi.list({ brand_id: brandId, limit: 200 }, agencyId, accessToken).catch(() => null),
      ]);
      setEntries(data);
      if (briefs) {
        const map: Record<string, string> = {};
        for (const b of briefs.items) map[b.id] = b.title;
        setBriefTitles(map);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [accessToken, agencyId, brandId, dateRange.start, dateRange.end]);

  useEffect(() => {
    load();
  }, [load]);

  const filteredEntries = useMemo(() => {
    return entries.filter((e) => {
      if (userFilter && e.user_id !== userFilter) return false;
      if (categoryFilter && e.category !== categoryFilter) return false;
      return true;
    });
  }, [entries, userFilter, categoryFilter]);

  const toggleOne = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // Toggles selection across exactly the currently filtered/rendered rows —
  // never anything outside `filteredEntries` (plan §12 mass-selection
  // safety: this can never reach across brands, date ranges, or the
  // full tenant).
  const toggleAll = () => {
    setSelected((prev) => {
      const allSelected = filteredEntries.length > 0 && filteredEntries.every((e) => prev.has(e.id));
      if (allSelected) return new Set();
      return new Set(filteredEntries.map((e) => e.id));
    });
  };

  const selectedSeconds = entries
    .filter((e) => selected.has(e.id))
    .reduce((sum, e) => sum + (e.duration_seconds ?? 0), 0);

  const handleCreateDraft = async () => {
    if (!accessToken || !agencyId || !brandId || selected.size === 0) return;
    setCreatingDraft(true);
    try {
      const invoice = await financeApi.createInvoiceDraft(
        { brand_id: brandId, time_entry_ids: Array.from(selected) },
        agencyId,
        accessToken
      );
      toast("Fatura taslağı oluşturuldu.", "success");
      router.push(`/dashboard/finance/invoices/${invoice.id}`);
    } catch (e) {
      const message = e instanceof ApiError ? (typeof e.detail === "string" ? e.detail : e.message) : "Taslak oluşturulamadı";
      toast(message, "error");
    } finally {
      setCreatingDraft(false);
    }
  };

  if (!isInitialized || !agencyId || !accessToken) return null;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex items-start justify-between gap-4 mb-6 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold text-text">Faturalandırılabilir Zaman</h1>
          <p className="text-sm text-text-muted mt-1">
            Kilitlenmiş, henüz faturalanmamış zaman kayıtlarını seçip fatura taslağı oluşturun.
          </p>
        </div>
        {canCreateDraft && (
          <Button onClick={handleCreateDraft} disabled={selected.size === 0} isLoading={creatingDraft}>
            <FileText className="w-4 h-4" />
            Fatura Taslağı Oluştur {selected.size > 0 && `(${selected.size})`}
          </Button>
        )}
      </div>

      {brandsLoading ? (
        <div className="h-10 bg-surface-2 rounded-lg animate-pulse max-w-xs mb-6" />
      ) : brandsError ? (
        <p className="text-sm text-danger mb-6">{brandsError}</p>
      ) : brands.length === 0 ? (
        <div className="text-center py-12 border border-dashed border-border rounded-xl">
          <Building2 className="w-8 h-8 text-text-muted/40 mx-auto mb-3" />
          <p className="text-sm text-text-muted">Henüz bir marka eklenmemiş.</p>
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-end gap-4 mb-2">
            <div className="w-full sm:w-56">
              <Select
                label="Marka"
                value={brandId}
                onChange={(e) => setBrandId(e.target.value)}
                options={brands.map((b) => ({ value: b.id, label: b.name }))}
              />
            </div>
            <div className="w-full sm:w-48">
              <Select
                label="Kullanıcı"
                value={userFilter}
                onChange={(e) => setUserFilter(e.target.value)}
                options={[
                  { value: "", label: "Tümü" },
                  ...members.map((m) => ({ value: m.user_id, label: m.user_full_name ?? m.user_email ?? m.user_id })),
                ]}
              />
            </div>
            <div className="w-full sm:w-48">
              <Select
                label="Kategori"
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value as TimeEntryCategory | "")}
                options={[{ value: "", label: "Tümü" }, ...TIME_CATEGORY_OPTIONS]}
              />
            </div>
          </div>

          <DateRangeFilter
            value={dateRange}
            onPresetChange={dateRange.setPreset}
            onCustomChange={dateRange.setCustomDates}
            onClear={dateRange.clear}
          />

          {selected.size > 0 && (
            <div className="mb-4 px-4 py-2.5 rounded-lg bg-accent/10 border border-accent/20 text-sm text-accent flex items-center justify-between">
              <span>{selected.size} kayıt seçildi</span>
              <span className="tabular-nums">{(selectedSeconds / 3600).toFixed(1)} saat</span>
            </div>
          )}

          {error ? (
            <div className="bg-danger/10 border border-danger/30 rounded-xl p-4 text-sm text-danger">{error}</div>
          ) : (
            <BillableTimeTable
              entries={filteredEntries}
              loading={loading}
              memberNames={memberNames}
              briefTitles={briefTitles}
              selected={selected}
              onToggleOne={toggleOne}
              onToggleAll={toggleAll}
              selectable={canCreateDraft}
            />
          )}
        </>
      )}
    </div>
  );
}

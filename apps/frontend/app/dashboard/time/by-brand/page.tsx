"use client";

import { Select } from "@/components/ui/select";
import { TimeBarChart } from "@/components/time-tracking/TimeBarChart";
import { DateRangeFilter } from "@/components/time-tracking/DateRangeFilter";
import { useDateRangeFilter } from "@/hooks/useDateRangeFilter";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { agencyApi, timeReportApi, type BrandRead, type BrandTimeSummary } from "@/lib/api-client";
import { useCallback, useEffect, useState } from "react";

export default function ByBrandTimeReportPage() {
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();
  const agencyId = activeAgency?.id ?? null;
  const dateRange = useDateRangeFilter();

  const [brands, setBrands] = useState<BrandRead[]>([]);
  const [brandId, setBrandId] = useState<string>("");
  const [summary, setSummary] = useState<BrandTimeSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken || !agencyId) return;
    agencyApi
      .listBrands(agencyId, accessToken)
      .then((list) => {
        setBrands(list);
        if (list.length > 0) setBrandId(list[0].id);
      })
      .catch(() => {});
  }, [accessToken, agencyId]);

  const load = useCallback(async () => {
    if (!accessToken || !agencyId || !brandId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await timeReportApi.getByBrand(
        brandId,
        agencyId,
        accessToken,
        dateRange.apiParams
      );
      setSummary(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [accessToken, agencyId, brandId, dateRange.apiParams]);

  useEffect(() => {
    load();
  }, [load]);

  if (!agencyId) return null;

  return (
    <div>
      <div className="mb-5 max-w-xs">
        <Select
          label="Marka"
          value={brandId}
          onChange={(e) => setBrandId(e.target.value)}
          options={brands.map((b) => ({ value: b.id, label: b.name }))}
        />
      </div>

      <DateRangeFilter
        value={dateRange}
        onPresetChange={dateRange.setPreset}
        onCustomChange={dateRange.setCustomDates}
        onClear={dateRange.clear}
      />

      {error ? (
        <div className="bg-danger/10 border border-danger/30 rounded-xl p-4 text-sm text-danger">
          {error}
        </div>
      ) : loading || !summary ? (
        <div className="h-48 bg-surface-2 rounded-xl animate-pulse" />
      ) : (
        <div className="bg-surface border border-border rounded-xl p-6">
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div>
              <p
                data-testid="brand-total-hours"
                className="text-2xl font-semibold text-text tabular-nums"
              >
                {summary.total_hours.toFixed(1)}s
              </p>
              <p className="text-xs text-text-muted mt-0.5">Toplam Süre</p>
            </div>
            <div>
              <p className="text-2xl font-semibold text-text tabular-nums">
                {summary.billable_hours.toFixed(1)}s
              </p>
              <p className="text-xs text-text-muted mt-0.5">Faturalandırılabilir</p>
            </div>
            <div>
              <p className="text-2xl font-semibold text-text tabular-nums">
                {summary.brief_count}
              </p>
              <p className="text-xs text-text-muted mt-0.5">Brief Sayısı</p>
            </div>
          </div>
          <TimeBarChart data={summary.category_breakdown} />
        </div>
      )}
    </div>
  );
}

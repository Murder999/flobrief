"use client";

import { RetainerSummaryCard } from "@/components/finance/RetainerSummaryCard";
import { SkeletonCard } from "@/components/ui/skeleton";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { agencyApi, financeApi, type BrandRead, type RetainerSummary } from "@/lib/api-client";
import { Repeat } from "lucide-react";
import { useEffect, useState } from "react";

interface RetainerBrand {
  brand: BrandRead;
  summary: RetainerSummary | null;
  error: string | null;
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <div className="w-16 h-16 bg-surface-2 rounded-2xl flex items-center justify-center mb-4">
        <Repeat className="w-7 h-7 text-text-muted" />
      </div>
      <p className="text-base font-medium text-text mb-1">Retainer modelinde marka yok</p>
      <p className="text-sm text-text-muted max-w-sm">
        Bu görünüm yalnızca aktif ticari koşulu &quot;Retainer&quot; olan markaları listeler. Finans
        Ayarları&apos;ndan bir markanın faturalama modelini Retainer olarak ayarlayın.
      </p>
    </div>
  );
}

/** Per-brand retainer consumption for the current period, for every brand
 * whose active `CommercialTerms.billing_model === "retainer"` (plan §4/§11).
 * There is no bulk "list retainer brands" backend endpoint, so this page
 * fans out one commercial-terms lookup per brand to determine eligibility,
 * then one retainer-summary lookup per eligible brand — acceptable at
 * agency-roster scale, matches the N+1-but-bounded pattern already used by
 * `FinanceSettingsPage`'s per-brand terms fetch. */
export default function RetainersPage() {
  const { accessToken } = useAuth();
  const { activeAgency, isInitialized } = useWorkspace();
  const agencyId = activeAgency?.id ?? null;

  const [rows, setRows] = useState<RetainerBrand[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken || !agencyId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);

    (async () => {
      try {
        const brands = await agencyApi.listBrands(agencyId, accessToken);
        const eligible: BrandRead[] = [];
        await Promise.all(
          brands.map(async (b) => {
            try {
              const terms = await financeApi.listCommercialTerms(b.id, agencyId, accessToken);
              const active = terms.find((t) => t.active);
              if (active?.billing_model === "retainer") eligible.push(b);
            } catch {
              /* skip brands whose terms can't be read (e.g. no access) */
            }
          })
        );

        const summaries = await Promise.all(
          eligible.map(async (brand) => {
            try {
              const summary = await financeApi.getRetainerSummary(brand.id, agencyId, accessToken);
              return { brand, summary, error: null } as RetainerBrand;
            } catch (e) {
              return {
                brand,
                summary: null,
                error: e instanceof Error ? e.message : "Retainer özeti yüklenemedi",
              } as RetainerBrand;
            }
          })
        );

        if (!cancelled) {
          summaries.sort((a, b) => a.brand.name.localeCompare(b.brand.name, "tr"));
          setRows(summaries);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Yüklenemedi");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [accessToken, agencyId]);

  if (!isInitialized || !agencyId || !accessToken) return null;

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-text">Retainer&apos;lar</h1>
        <p className="text-sm text-text-muted mt-1">
          Retainer modelindeki markaların bu dönemki dahil süre, kullanım ve aşım durumu.
        </p>
      </div>

      {error ? (
        <div className="bg-danger/10 border border-danger/30 rounded-xl p-4 text-sm text-danger">{error}</div>
      ) : loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : rows.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {rows.map(({ brand, summary, error: rowError }) =>
            summary ? (
              <RetainerSummaryCard key={brand.id} brandName={brand.name} summary={summary} />
            ) : (
              <div key={brand.id} className="bg-surface border border-border rounded-xl p-5">
                <p className="text-sm font-semibold text-text mb-1">{brand.name}</p>
                <p className="text-xs text-danger">{rowError}</p>
              </div>
            )
          )}
        </div>
      )}
    </div>
  );
}

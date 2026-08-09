"use client";

import { CommercialTermsForm } from "@/components/finance/CommercialTermsForm";
import { CostRateForm } from "@/components/finance/CostRateForm";
import { Select } from "@/components/ui/select";
import { SkeletonCard } from "@/components/ui/skeleton";
import { useWorkspace } from "@/context/workspace-context";
import { useAuth } from "@/hooks/useAuth";
import {
  agencyApi,
  financeApi,
  type AgencyMemberRead,
  type BrandRead,
  type CommercialTermsRead,
} from "@/lib/api-client";
import { canManageCommercialTerms, canViewCostRates } from "@/lib/finance";
import { Building2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

/** Finance settings — Phase 3 of the resource/finance plan (plan §14).
 * Two independent sections:
 *  1. Commercial terms, per brand — visible to anyone who can reach this
 *     page, editable by Owner/Admin (mirrors `COMMERCIAL_TERMS_MANAGE`).
 *  2. Cost rates — Owner-only, per plan §8's conservative default (not even
 *     Admin). The fetch itself (not just the render) is gated: `CostRateForm`
 *     is never mounted for a non-Owner viewer, so no cost-rate request is
 *     ever made from a session that can't see the result. */
export default function FinanceSettingsPage() {
  const { accessToken } = useAuth();
  const { activeAgency, isInitialized } = useWorkspace();
  const agencyId = activeAgency?.id ?? null;
  const role = activeAgency?.member_role ?? null;
  const canManageTerms = canManageCommercialTerms(role);
  const showCostRates = canViewCostRates(role);

  const [brands, setBrands] = useState<BrandRead[]>([]);
  const [selectedBrandId, setSelectedBrandId] = useState<string | null>(null);
  const [brandsLoading, setBrandsLoading] = useState(true);
  const [brandsError, setBrandsError] = useState<string | null>(null);

  const [members, setMembers] = useState<AgencyMemberRead[]>([]);

  const [currentTerms, setCurrentTerms] = useState<CommercialTermsRead | null>(null);
  const [termsLoading, setTermsLoading] = useState(true);
  const [termsError, setTermsError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken || !agencyId) return;
    setBrandsLoading(true);
    setBrandsError(null);
    agencyApi
      .listBrands(agencyId, accessToken)
      .then((list) => {
        setBrands(list);
        setSelectedBrandId((prev) => prev ?? list[0]?.id ?? null);
      })
      .catch((e) => setBrandsError(e instanceof Error ? e.message : "Markalar yüklenemedi"))
      .finally(() => setBrandsLoading(false));
  }, [accessToken, agencyId]);

  // Members are only needed for the Owner-only cost-rate target picker —
  // gate this fetch behind `showCostRates` too, not just the section render.
  useEffect(() => {
    if (!accessToken || !agencyId || !showCostRates) return;
    agencyApi
      .listMembers(agencyId, accessToken)
      .then((mems) => setMembers(mems.filter((m) => m.status === "active")))
      .catch(() => {
        /* non-fatal: cost-rate target select just falls back to empty */
      });
  }, [accessToken, agencyId, showCostRates]);

  const loadTerms = useCallback(async () => {
    if (!accessToken || !agencyId || !selectedBrandId) return;
    setTermsLoading(true);
    setTermsError(null);
    try {
      const list = await financeApi.listCommercialTerms(selectedBrandId, agencyId, accessToken);
      setCurrentTerms(list.find((t) => t.active) ?? null);
    } catch (e) {
      setTermsError(e instanceof Error ? e.message : "Ticari koşullar yüklenemedi");
    } finally {
      setTermsLoading(false);
    }
  }, [accessToken, agencyId, selectedBrandId]);

  useEffect(() => {
    loadTerms();
  }, [loadTerms]);

  if (!isInitialized || !agencyId || !accessToken) return null;

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-text">Finans Ayarları</h1>
        <p className="text-sm text-text-muted mt-1">
          Marka bazında ticari koşulları ve iç maliyet oranlarını yönetin.
        </p>
      </div>

      {brandsLoading ? (
        <div className="space-y-4">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : brandsError ? (
        <p className="text-sm text-danger">{brandsError}</p>
      ) : brands.length === 0 ? (
        <div className="text-center py-12 border border-dashed border-border rounded-xl">
          <Building2 className="w-8 h-8 text-text-muted/40 mx-auto mb-3" />
          <p className="text-sm text-text-muted">Henüz bir marka eklenmemiş.</p>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="max-w-xs">
            <Select
              label="Marka"
              value={selectedBrandId ?? ""}
              onChange={(e) => setSelectedBrandId(e.target.value)}
              options={brands.map((b) => ({ value: b.id, label: b.name }))}
            />
          </div>

          {termsLoading ? (
            <SkeletonCard />
          ) : termsError ? (
            <p className="text-sm text-danger">{termsError}</p>
          ) : (
            selectedBrandId && (
              <CommercialTermsForm
                key={selectedBrandId}
                brandId={selectedBrandId}
                agencyId={agencyId}
                accessToken={accessToken}
                currentTerms={currentTerms}
                canManage={canManageTerms}
                onSaved={(terms) => setCurrentTerms(terms)}
              />
            )
          )}
        </div>
      )}

      {showCostRates && <CostRateForm agencyId={agencyId} accessToken={accessToken} members={members} />}
    </div>
  );
}

"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { workspaceApi } from "@/lib/api-client";
import type { WorkspaceAgency, WorkspaceBrand } from "@/lib/workspace";
import {
  getStoredAgencyId,
  getStoredBrandId,
  storeAgencyId,
  storeBrandId,
} from "@/lib/workspace";
import { useAuth } from "@/hooks/useAuth";

interface WorkspaceContextValue {
  agencies: WorkspaceAgency[];
  brands: WorkspaceBrand[];
  activeAgency: WorkspaceAgency | null;
  activeBrand: WorkspaceBrand | null;
  isLoading: boolean;
  isInitialized: boolean;
  switchAgency: (agencyId: string) => void;
  switchBrand: (brandId: string) => void;
  refreshWorkspaces: () => Promise<void>;
}

const WorkspaceCtx = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { user, accessToken } = useAuth();
  const [agencies, setAgencies] = useState<WorkspaceAgency[]>([]);
  const [brands, setBrands] = useState<WorkspaceBrand[]>([]);
  const [activeAgencyId, setActiveAgencyId] = useState<string | null>(null);
  const [activeBrandId, setActiveBrandId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);

  const refreshWorkspaces = useCallback(async () => {
    if (!accessToken) return;
    setIsLoading(true);
    try {
      const data = await workspaceApi.list(accessToken);
      const agencyList = Array.isArray(data?.agencies) ? data.agencies : [];
      const brandList = Array.isArray(data?.brands) ? data.brands : [];
      setAgencies(agencyList);
      setBrands(brandList);

      const stored = getStoredAgencyId();
      const found = agencyList.find((a) => a.id === stored);
      if (found) {
        setActiveAgencyId(found.id);
      } else if (agencyList.length > 0) {
        const first = agencyList[0];
        setActiveAgencyId(first.id);
        storeAgencyId(first.id);
      } else {
        setActiveAgencyId(null);
      }

      const storedBrand = getStoredBrandId();
      const foundBrand = brandList.find((brand) => brand.id === storedBrand);
      if (foundBrand) {
        setActiveBrandId(foundBrand.id);
      } else if (brandList.length > 0) {
        const firstBrand = brandList[0];
        setActiveBrandId(firstBrand.id);
        storeBrandId(firstBrand.id);
      } else {
        setActiveBrandId(null);
      }
    } catch {
      // silent — workspace load failure should not crash the app
    } finally {
      setIsLoading(false);
      setIsInitialized(true);
    }
  }, [accessToken]);

  useEffect(() => {
    if (user && user.user_type !== "platform_admin" && accessToken) {
      refreshWorkspaces();
    } else if (user) {
      setAgencies([]);
      setBrands([]);
      setActiveAgencyId(null);
      setActiveBrandId(null);
      setIsLoading(false);
      setIsInitialized(true);
    } else {
      setAgencies([]);
      setBrands([]);
      setActiveAgencyId(null);
      setActiveBrandId(null);
      setIsLoading(false);
      setIsInitialized(false);
    }
  }, [user, accessToken, refreshWorkspaces]);

  const switchAgency = useCallback((agencyId: string) => {
    setActiveAgencyId(agencyId);
    storeAgencyId(agencyId);
  }, []);

  const switchBrand = useCallback((brandId: string) => {
    setActiveBrandId(brandId);
    storeBrandId(brandId);
  }, []);

  const activeAgency = (agencies ?? []).find((a) => a.id === activeAgencyId) ?? null;
  const activeBrand = (brands ?? []).find((brand) => brand.id === activeBrandId) ?? null;

  return (
    <WorkspaceCtx.Provider
      value={{
        agencies,
        brands,
        activeAgency,
        activeBrand,
        isLoading,
        isInitialized,
        switchAgency,
        switchBrand,
        refreshWorkspaces,
      }}
    >
      {children}
    </WorkspaceCtx.Provider>
  );
}

export function useWorkspace(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceCtx);
  if (!ctx) throw new Error("useWorkspace must be used inside WorkspaceProvider");
  return ctx;
}

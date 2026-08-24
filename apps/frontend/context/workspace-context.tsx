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
import type { WorkspaceAgency } from "@/lib/workspace";
import { getStoredAgencyId, storeAgencyId } from "@/lib/workspace";
import { useAuth } from "@/hooks/useAuth";

interface WorkspaceContextValue {
  agencies: WorkspaceAgency[];
  activeAgency: WorkspaceAgency | null;
  isLoading: boolean;
  isInitialized: boolean;
  switchAgency: (agencyId: string) => void;
  refreshWorkspaces: () => Promise<void>;
}

const WorkspaceCtx = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { user, accessToken } = useAuth();
  const [agencies, setAgencies] = useState<WorkspaceAgency[]>([]);
  const [activeAgencyId, setActiveAgencyId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);

  const refreshWorkspaces = useCallback(async () => {
    if (!accessToken) return;
    setIsLoading(true);
    try {
      const data = await workspaceApi.list(accessToken);
      const agencyList = Array.isArray(data?.agencies) ? data.agencies : [];
      setAgencies(agencyList);

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
    } catch {
      // silent — workspace load failure should not crash the app
    } finally {
      setIsLoading(false);
      setIsInitialized(true);
    }
  }, [accessToken]);

  useEffect(() => {
    if (user?.user_type === "agency_user" && accessToken) {
      refreshWorkspaces();
    } else if (user) {
      // Brand and platform identities never carry agency workspace state.
      setAgencies([]);
      setActiveAgencyId(null);
      setIsLoading(false);
      setIsInitialized(true);
    } else {
      setAgencies([]);
      setActiveAgencyId(null);
      setIsLoading(false);
      setIsInitialized(false);
    }
  }, [user, accessToken, refreshWorkspaces]);

  const switchAgency = useCallback((agencyId: string) => {
    setActiveAgencyId(agencyId);
    storeAgencyId(agencyId);
  }, []);

  const activeAgency = (agencies ?? []).find((a) => a.id === activeAgencyId) ?? null;

  return (
    <WorkspaceCtx.Provider
      value={{ agencies, activeAgency, isLoading, isInitialized, switchAgency, refreshWorkspaces }}
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

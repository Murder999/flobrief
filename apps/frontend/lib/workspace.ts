import { translateCurrent } from "@/lib/i18n/current";

const ACTIVE_AGENCY_KEY = "flobrief_active_agency_id";

export function getStoredAgencyId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACTIVE_AGENCY_KEY);
}

export function storeAgencyId(agencyId: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(ACTIVE_AGENCY_KEY, agencyId);
}

export function clearStoredAgencyId(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(ACTIVE_AGENCY_KEY);
}

const PENDING_PLAN_KEY = "flobrief_pending_plan";

export interface PendingPlan {
  planId: string;
  yearly: boolean;
}

export function storePendingPlan(plan: PendingPlan): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(PENDING_PLAN_KEY, JSON.stringify(plan));
}

export function getPendingPlan(): PendingPlan | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(PENDING_PLAN_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as PendingPlan;
  } catch {
    return null;
  }
}

export function clearPendingPlan(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(PENDING_PLAN_KEY);
}

export interface WorkspaceAgency {
  id: string;
  name: string;
  slug: string;
  status: string;
  logo_url: string | null;
  member_role: string;
  member_status: string;
}

export interface WorkspaceBrand {
  id: string;
  agency_id: string | null;
  name: string;
  slug: string;
  status: string;
  member_role: string;
  member_status: string;
}

export interface WorkspaceList {
  agencies: WorkspaceAgency[];
  brands: WorkspaceBrand[];
}

export interface PermissionResponse {
  user_type: string;
  agency_id: string | null;
  role: string | null;
  permissions: string[];
}

export const ROLE_LABELS: Record<string, string> = {
  get owner() { return translateCurrent("settings.role.owner"); },
  get admin() { return translateCurrent("settings.role.admin"); },
  get brand_manager() { return translateCurrent("settings.role.brandManager"); },
  get designer() { return translateCurrent("settings.role.designer"); },
  get developer() { return translateCurrent("settings.role.developer"); },
  get social_media_manager() { return translateCurrent("settings.role.socialMedia"); },
  get viewer() { return translateCurrent("settings.role.viewer"); },
  get brand_owner() { return translateCurrent("settings.role.brandOwner"); },
  get brand_viewer() { return translateCurrent("settings.role.viewer"); },
  get external_approver() { return translateCurrent("settings.role.externalApprover"); },
};

export const ROLE_COLORS: Record<string, string> = {
  owner: "text-accent bg-accent/10",
  admin: "text-purple-400 bg-purple-400/10",
  brand_manager: "text-blue-400 bg-blue-400/10",
  designer: "text-pink-400 bg-pink-400/10",
  developer: "text-green-400 bg-green-400/10",
  social_media_manager: "text-yellow-400 bg-yellow-400/10",
  viewer: "text-text-muted bg-surface-2",
  brand_owner: "text-accent bg-accent/10",
  brand_viewer: "text-text-muted bg-surface-2",
  external_approver: "text-orange-400 bg-orange-400/10",
};

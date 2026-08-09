import type { ComponentType } from "react";

export type NavIcon = ComponentType<{ className?: string }>;

export interface NavDrawerItem {
  href: string;
  label: string;
  icon: NavIcon;
  exact?: boolean;
  /** Truthy/positive renders a count pill; `true` alone renders a plain dot. */
  badge?: number | boolean;
}

export interface NavDrawerGroup {
  /** null renders no group heading (e.g. the first, single-item group). */
  label: string | null;
  items: NavDrawerItem[];
}

export interface BottomNavItem {
  href: string;
  label: string;
  icon: NavIcon;
  exact?: boolean;
  badge?: number;
}

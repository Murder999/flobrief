"use client";

/**
 * Bridges the onboarding spotlight (rendered as a sibling of
 * `ResponsiveAppShell`, e.g. `<AgencyOnboardingWizard />` in
 * `app/dashboard/layout.tsx` — not a descendant) to the mobile nav drawer's
 * open/close state, which is owned locally inside `ResponsiveAppShell`
 * (`useState` in that component). A walkthrough step whose real DOM anchor
 * only exists in the mobile drawer (`MobileNavigationDrawer` only renders
 * its nav links while `isOpen`) needs the drawer forced open before
 * `document.querySelector`/spotlight tracking can ever find it — this tiny
 * pub/sub is that one signal, deliberately outside React context/props
 * since the two components don't share a parent that could hold the state.
 */

type Listener = (open: boolean) => void;

const listeners = new Set<Listener>();

export function requestMobileDrawerOpen(open: boolean): void {
  listeners.forEach((listener) => listener(open));
}

export function subscribeMobileDrawerRequests(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

"use client";

import { useEffect, useRef } from "react";
import { onboardingApi, brandOnboardingApi } from "@/lib/api-client";

interface UseOnboardingPageSeenOptions {
  stepKey: string | null;
  variant: "agency" | "brand";
  agencyId?: string | null;
  accessToken: string | null;
  enabled?: boolean;
}

/**
 * Marks an onboarding "view" step seen once the real page/component that
 * represents it actually mounts — organic navigation should count the same
 * as clicking the wizard's own "Şimdi Yap" CTA. Idempotent both client-side
 * (a ref guard fires it at most once per stepKey per mount) and server-side
 * (`mark_step_seen` only ever sets `first_seen_at` once), so calling it from
 * several pages that map to the same step key, or re-rendering, is safe —
 * no dedupe bookkeeping beyond the ref is needed.
 */
export function useOnboardingPageSeen({
  stepKey,
  variant,
  agencyId,
  accessToken,
  enabled = true,
}: UseOnboardingPageSeenOptions) {
  const firedRef = useRef<string | null>(null);

  useEffect(() => {
    if (!enabled || !stepKey || !accessToken) return;
    if (variant === "agency" && !agencyId) return;
    if (firedRef.current === stepKey) return;
    firedRef.current = stepKey;

    const call =
      variant === "agency"
        ? onboardingApi.markStepSeen(stepKey, agencyId as string, accessToken)
        : brandOnboardingApi.markStepSeen(stepKey, accessToken);

    call.catch(() => {
      // A role-inaccessible step key 404s, and a transient network failure
      // can happen too — both are harmless here (onboarding is a
      // non-critical enhancement layer, and the wizard's own explicit
      // "seen" call is still a fallback path), so allow a retry on the next
      // mount instead of leaving the step permanently unmarked client-side.
      firedRef.current = null;
    });
  }, [enabled, stepKey, variant, agencyId, accessToken]);
}

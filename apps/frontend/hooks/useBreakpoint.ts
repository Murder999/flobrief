"use client";

import { useEffect, useState } from "react";

const TABLET_QUERY = "(max-width: 1023px)";
const MOBILE_QUERY = "(max-width: 767px)";

export interface Breakpoint {
  isMobile: boolean;
  isTablet: boolean;
  isDesktop: boolean;
}

function readBreakpoint(): Breakpoint {
  if (typeof window === "undefined") {
    return { isMobile: false, isTablet: false, isDesktop: true };
  }
  const belowTablet = window.matchMedia(TABLET_QUERY).matches;
  const belowMobile = window.matchMedia(MOBILE_QUERY).matches;
  return {
    isMobile: belowMobile,
    isTablet: belowTablet && !belowMobile,
    isDesktop: !belowTablet,
  };
}

/**
 * Mirrors the Tailwind `md`/`lg` breakpoints (768px / 1024px) used for the
 * shell's CSS-driven show/hide. Only consume this where a decision actually
 * changes DOM structure (e.g. Modal choosing a bottom sheet vs a centered
 * dialog) — plain visibility toggles should stay pure CSS to avoid a
 * hydration flash.
 */
export function useBreakpoint(): Breakpoint {
  const [breakpoint, setBreakpoint] = useState<Breakpoint>(readBreakpoint);

  useEffect(() => {
    const tabletQuery = window.matchMedia(TABLET_QUERY);
    const mobileQuery = window.matchMedia(MOBILE_QUERY);
    const update = () => setBreakpoint(readBreakpoint());
    update();
    tabletQuery.addEventListener("change", update);
    mobileQuery.addEventListener("change", update);
    return () => {
      tabletQuery.removeEventListener("change", update);
      mobileQuery.removeEventListener("change", update);
    };
  }, []);

  return breakpoint;
}

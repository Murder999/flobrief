"use client";

import type { ReactNode } from "react";

interface SafeAreaContainerProps {
  children: ReactNode;
  top?: boolean;
  bottom?: boolean;
  left?: boolean;
  right?: boolean;
  /** Fallback padding used on devices with no safe-area inset (e.g. a
   * square-cornered Android phone) — `max()` picks whichever is larger, so
   * this is a floor, not something added on top of the inset. */
  minTop?: string;
  minBottom?: string;
  minLeft?: string;
  minRight?: string;
  className?: string;
}

/**
 * Applies `env(safe-area-inset-*)` padding on the requested edges via
 * `max(minSide, env(...))`, so normal devices keep the design's minimum
 * padding and notched/rounded-corner devices get whichever is larger.
 * Requires `viewport-fit=cover` (set in app/layout.tsx) for the env()
 * values to resolve to anything but 0.
 */
export function SafeAreaContainer({
  children,
  top,
  bottom,
  left,
  right,
  minTop = "0px",
  minBottom = "0px",
  minLeft = "0px",
  minRight = "0px",
  className,
}: SafeAreaContainerProps) {
  return (
    <div
      className={className}
      style={{
        paddingTop: top ? `max(${minTop}, env(safe-area-inset-top))` : undefined,
        paddingBottom: bottom ? `max(${minBottom}, env(safe-area-inset-bottom))` : undefined,
        paddingLeft: left ? `max(${minLeft}, env(safe-area-inset-left))` : undefined,
        paddingRight: right ? `max(${minRight}, env(safe-area-inset-right))` : undefined,
      }}
    >
      {children}
    </div>
  );
}

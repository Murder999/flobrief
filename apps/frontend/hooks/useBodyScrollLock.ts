"use client";

import { useEffect } from "react";

let lockCount = 0;
let previousOverflow = "";

function acquireLock() {
  if (lockCount === 0) {
    previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
  }
  lockCount += 1;
}

function releaseLock() {
  lockCount = Math.max(0, lockCount - 1);
  if (lockCount === 0) {
    document.body.style.overflow = previousOverflow;
  }
}

/**
 * Ref-counted body scroll lock so two overlays open at once (e.g. a Modal
 * opened from inside an open Drawer) don't clobber each other's restore —
 * the body only unlocks once every locker has released.
 */
export function useBodyScrollLock(active: boolean): void {
  useEffect(() => {
    if (!active) return;
    acquireLock();
    return () => releaseLock();
  }, [active]);
}

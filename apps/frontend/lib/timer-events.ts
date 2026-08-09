/** Tiny pub-sub so independent time-tracking UI surfaces (the sidebar
 * GlobalTimerWidget, the brief-detail quick-start button, any future
 * surface) stay in sync when a timer starts or stops anywhere on the page —
 * without a page reload and without introducing a global state library for
 * one boolean-ish fact. */

const EVENT_NAME = "flobrief:timer-changed";

export function emitTimerChanged(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(EVENT_NAME));
  }
}

export function onTimerChanged(callback: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener(EVENT_NAME, callback);
  return () => window.removeEventListener(EVENT_NAME, callback);
}

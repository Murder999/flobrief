"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

interface SpotlightOverlayProps {
  /** CSS selector for the real DOM anchor to highlight, e.g. `[data-onboarding-target="/dashboard/brands"]`. Null renders the no-target fallback immediately (steps with no persistent nav anchor, e.g. contextual annotation/comment steps). */
  target: string | null;
  title: string;
  description: string;
  stepNumber: number;
  totalSteps: number;
  onNext: () => void;
  onBack?: () => void;
  onLater: () => void;
  /** Shown once the target selector fails to resolve within the timeout, or when `target` is null — lets the user jump straight to the relevant page instead of leaving the tour stuck. */
  onOpenPage?: () => void;
}

const FALLBACK_TIMEOUT_MS = 3000;
const HIGHLIGHT_PADDING = 6;
const TOOLTIP_WIDTH = 320;

/** Desktop sidebar and mobile drawer share the same
 * `data-onboarding-target` selector value (the nav href) — the sidebar
 * link stays in the DOM even when CSS-hidden below `lg`, and the drawer's
 * matching link only exists once it's open. `document.querySelector` alone
 * always returns document order's first match regardless of visibility, so
 * a plain query would keep resolving to the hidden sidebar link on mobile.
 * `offsetParent === null` is true for `display:none` elements (and their
 * hidden ancestors) and false for normal flow/`position:fixed` elements in
 * a rendered document — exactly what's needed to skip the hidden one. */
function findVisibleTarget(selector: string): HTMLElement | null {
  const candidates = document.querySelectorAll<HTMLElement>(selector);
  for (const el of candidates) {
    if (el.offsetParent !== null) return el;
  }
  return null;
}

/**
 * Portal-rendered, config-driven spotlight: dims the page and cuts a
 * highlight window around a real DOM node (via a giant box-shadow, not a
 * clip-path mask, so it survives arbitrary target shapes), positions a
 * tooltip next to it, and falls back to a text-only panel + "Sayfayı Aç"
 * button when the target selector never resolves (bounded by a
 * MutationObserver + timeout, not an indefinite wait).
 */
export function SpotlightOverlay({
  target,
  title,
  description,
  stepNumber,
  totalSteps,
  onNext,
  onBack,
  onLater,
  onOpenPage,
}: SpotlightOverlayProps) {
  const [rect, setRect] = useState<DOMRect | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    setRect(null);
    setNotFound(false);
    if (!target) {
      setNotFound(true);
      return;
    }

    let settled = false;
    let resizeObserver: ResizeObserver | null = null;
    let mutationObserver: MutationObserver | null = null;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    const trackElement = (el: Element) => {
      settled = true;
      const update = () => setRect(el.getBoundingClientRect());
      update();

      const bounds = el.getBoundingClientRect();
      const inView = bounds.top >= 0 && bounds.bottom <= window.innerHeight;
      if (!inView) {
        const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        el.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "center" });
      }

      resizeObserver = new ResizeObserver(update);
      resizeObserver.observe(el);
      window.addEventListener("resize", update);
      window.addEventListener("scroll", update, true);
      return () => {
        resizeObserver?.disconnect();
        window.removeEventListener("resize", update);
        window.removeEventListener("scroll", update, true);
      };
    };

    let untrack: (() => void) | undefined;
    const existing = findVisibleTarget(target);
    if (existing) {
      untrack = trackElement(existing);
    } else {
      mutationObserver = new MutationObserver(() => {
        if (settled) return;
        const found = findVisibleTarget(target);
        if (found) {
          untrack = trackElement(found);
          mutationObserver?.disconnect();
          if (timeoutId) clearTimeout(timeoutId);
        }
      });
      mutationObserver.observe(document.body, { childList: true, subtree: true });
      timeoutId = setTimeout(() => {
        if (!settled) {
          setNotFound(true);
          mutationObserver?.disconnect();
        }
      }, FALLBACK_TIMEOUT_MS);
    }

    return () => {
      mutationObserver?.disconnect();
      if (timeoutId) clearTimeout(timeoutId);
      untrack?.();
    };
  }, [target]);

  if (typeof document === "undefined") return null;

  const highlight = rect
    ? {
        top: rect.top - HIGHLIGHT_PADDING,
        left: rect.left - HIGHLIGHT_PADDING,
        width: rect.width + HIGHLIGHT_PADDING * 2,
        height: rect.height + HIGHLIGHT_PADDING * 2,
      }
    : null;

  // Clamp the tooltip's own width to the viewport (minus 16px margin each
  // side) before using it in any position math — on a ≤336px-wide screen
  // the un-clamped 320px width previously overflowed the right edge even
  // though `left` itself was clamped.
  const tooltipWidth = Math.min(TOOLTIP_WIDTH, window.innerWidth - 32);

  let tooltipStyle: React.CSSProperties = {
    top: 96,
    left: Math.max(16, Math.min(96, window.innerWidth - tooltipWidth - 16)),
  };
  if (highlight) {
    const preferRight = highlight.left + highlight.width + tooltipWidth + 24 < window.innerWidth;
    tooltipStyle = preferRight
      ? { top: Math.max(16, highlight.top), left: highlight.left + highlight.width + 16 }
      : {
          top: highlight.top + highlight.height + 12,
          left: Math.max(16, Math.min(highlight.left, window.innerWidth - tooltipWidth - 16)),
        };
  }

  return createPortal(
    <div className="fixed inset-0 z-[120]" role="dialog" aria-label={title}>
      {highlight ? (
        <div
          className="fixed rounded-xl border-2 pointer-events-none transition-[top,left,width,height] duration-150"
          style={{
            ...highlight,
            boxShadow: "0 0 0 9999px rgba(15,15,23,0.55)",
            borderColor: "rgba(124,58,237,0.55)",
          }}
        />
      ) : (
        <div className="fixed inset-0 bg-black/40" />
      )}

      <div
        className="fixed rounded-2xl border border-border bg-surface shadow-2xl p-4 animate-in fade-in duration-150"
        style={{ width: tooltipWidth, ...tooltipStyle }}
      >
        <p className="text-[10px] font-semibold text-accent tracking-wide mb-1">
          ADIM {stepNumber}/{totalSteps}
        </p>
        <h3 className="text-sm font-semibold text-text mb-1">{title}</h3>
        <p className="text-xs text-text-muted leading-relaxed mb-3">{description}</p>

        {notFound && (
          <p className="text-[11px] text-text-muted mb-2">
            Bu adımın hedefi şu an ekranda değil.
            {onOpenPage ? " Sayfayı doğrudan açabilirsiniz." : ""}
          </p>
        )}

        {notFound && onOpenPage && (
          <button
            type="button"
            onClick={onOpenPage}
            className="w-full mb-2 px-3 py-2 text-xs font-semibold text-white bg-accent hover:bg-accent-hover rounded-lg transition-colors"
          >
            Sayfayı Aç
          </button>
        )}

        <div className="flex items-center justify-between gap-2">
          {onBack ? (
            <button type="button" onClick={onBack} className="text-xs text-text-muted hover:text-text transition-colors">
              Geri
            </button>
          ) : (
            <span />
          )}
          <div className="flex items-center gap-3">
            <button type="button" onClick={onLater} className="text-xs text-text-muted hover:text-text transition-colors">
              Daha Sonra
            </button>
            <button
              type="button"
              onClick={onNext}
              className="px-3 py-1.5 text-xs font-semibold text-white bg-accent hover:bg-accent-hover rounded-lg transition-colors"
            >
              İleri
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}

"use client";

import { useRef, useState, useCallback, useEffect, useLayoutEffect } from "react";
import { cn } from "@/lib/utils";
import type { AnnotationRead } from "@/lib/api-client";
import { useAuthBlob } from "./MediaPreview";
import { useLocale } from "@/context/locale-context";

interface AnnotationCanvasProps {
  assetId: string;
  accessToken: string;
  annotations: AnnotationRead[];
  activeAnnotationId?: string | null;
  annotationMode: boolean;
  onCanvasClick?: (xPercent: number, yPercent: number) => void;
  onAnnotationClick?: (annotation: AnnotationRead) => void;
  onExitAnnotationMode?: () => void;
  className?: string;
  /** Pending, unsaved pin position (image-relative percent) — shows a temporary marker + composer popover. */
  newPinDraft?: { x: number; y: number } | null;
  /** Renders the "new revision point" composer content; positioned by this canvas, owned by the caller. */
  renderNewPinComposer?: () => React.ReactNode;
  onCloseNewPinComposer?: () => void;
  /** Renders the detail/reply popover content for the active existing annotation. */
  renderAnnotationPopover?: (annotation: AnnotationRead) => React.ReactNode;
  onCloseAnnotationPopover?: () => void;
  /** Annotation id to briefly pulse (deep-link focus from a notification). */
  pulseAnnotationId?: string | null;
}

interface RenderedImageRect {
  offsetX: number;
  offsetY: number;
  width: number;
  height: number;
}

const TYPE_COLORS: Record<string, string> = {
  revision: "bg-warning border-warning text-white",
  approval_note: "bg-success border-success text-white",
  general: "bg-accent border-accent text-white",
};

const MOBILE_BREAKPOINT_PX = 640;

/** Computes the actual on-screen rect of an `object-fit: contain` image within its container. */
function computeContainRect(
  containerWidth: number,
  containerHeight: number,
  naturalWidth: number,
  naturalHeight: number,
): RenderedImageRect {
  if (!containerWidth || !containerHeight || !naturalWidth || !naturalHeight) {
    return { offsetX: 0, offsetY: 0, width: containerWidth, height: containerHeight };
  }
  const scale = Math.min(containerWidth / naturalWidth, containerHeight / naturalHeight);
  const width = naturalWidth * scale;
  const height = naturalHeight * scale;
  return {
    offsetX: (containerWidth - width) / 2,
    offsetY: (containerHeight - height) / 2,
    width,
    height,
  };
}

// ── Anchored popover: flips/clamps to stay inside the scene, arrow points at the marker ──

interface PopoverBubbleProps {
  anchor: { x: number; y: number };
  containerSize: { width: number; height: number };
  compact: boolean;
  onRequestClose: () => void;
  children: React.ReactNode;
  ariaLabel: string;
}

function PopoverBubble({ anchor, containerSize, compact, onRequestClose, children, ariaLabel }: PopoverBubbleProps) {
  const popRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number; arrowSide: "left" | "right" } | null>(null);

  useLayoutEffect(() => {
    if (compact) {
      setPos(null);
      return;
    }
    const pop = popRef.current;
    if (!pop || !containerSize.width || !containerSize.height) return;
    const margin = 10;
    const gap = 16;
    const w = pop.offsetWidth;
    const h = pop.offsetHeight;

    let left = anchor.x + gap;
    let arrowSide: "left" | "right" = "left";
    if (left + w > containerSize.width - margin) {
      left = anchor.x - gap - w;
      arrowSide = "right";
    }
    left = Math.min(Math.max(margin, left), Math.max(margin, containerSize.width - w - margin));

    let top = anchor.y - h / 2;
    top = Math.max(margin, top);
    if (top + h > containerSize.height - margin) {
      top = Math.max(margin, containerSize.height - h - margin);
    }

    setPos({ left, top, arrowSide });
    // Re-measure whenever the anchor, container, or popover content changes size.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [anchor.x, anchor.y, containerSize.width, containerSize.height, compact, children]);

  if (compact) {
    return (
      <div
        ref={popRef}
        data-annotation-popover="true"
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel}
        className="fixed inset-x-0 bottom-0 z-50 rounded-t-2xl border-t border-border bg-surface shadow-modal"
        onClick={(e) => e.stopPropagation()}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="mx-auto mt-2 h-1 w-10 rounded-full bg-border" />
        <div className="max-h-[70vh] overflow-y-auto p-4" style={{ paddingBottom: "max(1rem, env(safe-area-inset-bottom))" }}>
          {children}
        </div>
      </div>
    );
  }

  return (
    <div
      ref={popRef}
      data-annotation-popover="true"
      role="dialog"
      aria-modal="false"
      aria-label={ariaLabel}
      className={cn(
        "absolute z-30 w-[290px] max-w-[calc(100%-20px)] rounded-xl border border-border bg-surface shadow-modal transition-opacity duration-100",
        pos ? "opacity-100" : "opacity-0 pointer-events-none",
      )}
      style={{ left: pos ? pos.left : anchor.x, top: pos ? pos.top : anchor.y }}
      onClick={(e) => e.stopPropagation()}
      onMouseDown={(e) => e.stopPropagation()}
    >
      {pos && (
        <span
          aria-hidden="true"
          className={cn(
            "absolute top-1/2 -translate-y-1/2 h-2.5 w-2.5 rotate-45 border-border bg-surface",
            pos.arrowSide === "left" ? "-left-[5px] border-l border-b" : "-right-[5px] border-r border-t",
          )}
        />
      )}
      <div className="max-h-[380px] overflow-y-auto p-3.5">{children}</div>
    </div>
  );
}

export default function AnnotationCanvas({
  assetId,
  accessToken,
  annotations,
  activeAnnotationId,
  annotationMode,
  onCanvasClick,
  onAnnotationClick,
  onExitAnnotationMode,
  className,
  newPinDraft,
  renderNewPinComposer,
  onCloseNewPinComposer,
  renderAnnotationPopover,
  onCloseAnnotationPopover,
  pulseAnnotationId,
}: AnnotationCanvasProps) {
  const { t } = useLocale();
  const containerRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const markerButtonRefs = useRef<Map<string, HTMLButtonElement>>(new Map());
  const { blobUrl, loading } = useAuthBlob(assetId, accessToken);
  const [hoverPin, setHoverPin] = useState<string | null>(null);
  const [renderedRect, setRenderedRect] = useState<RenderedImageRect | null>(null);
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
  const [isMobile, setIsMobile] = useState(false);

  const recomputeRect = useCallback(() => {
    const container = containerRef.current;
    const img = imgRef.current;
    if (!container) return;
    setContainerSize({ width: container.clientWidth, height: container.clientHeight });
    if (!img || !img.naturalWidth || !img.naturalHeight) return;
    setRenderedRect(
      computeContainRect(
        container.clientWidth,
        container.clientHeight,
        img.naturalWidth,
        img.naturalHeight,
      ),
    );
  }, []);

  // Recompute on container resize (modal resize, fullscreen, breakpoint changes).
  useEffect(() => {
    const container = containerRef.current;
    if (!container || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => recomputeRect());
    observer.observe(container);
    return () => observer.disconnect();
  }, [recomputeRect]);

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < MOBILE_BREAKPOINT_PX);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  const closeNewPin = useCallback(() => onCloseNewPinComposer?.(), [onCloseNewPinComposer]);
  const closeAnnotationPopover = useCallback(() => {
    onCloseAnnotationPopover?.();
    if (activeAnnotationId) markerButtonRefs.current.get(activeAnnotationId)?.focus();
  }, [onCloseAnnotationPopover, activeAnnotationId]);

  // Escape: closes an open popover first; only exits annotation mode once nothing is open.
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (newPinDraft) {
        closeNewPin();
        return;
      }
      if (activeAnnotationId) {
        closeAnnotationPopover();
        return;
      }
      if (annotationMode) onExitAnnotationMode?.();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [newPinDraft, activeAnnotationId, annotationMode, onExitAnnotationMode, closeNewPin, closeAnnotationPopover]);

  // Clicking outside the scene entirely (toolbar, sidebar list, page) cancels an open popover.
  useEffect(() => {
    if (!newPinDraft && !activeAnnotationId) return;
    const handler = (e: MouseEvent) => {
      if (containerRef.current?.contains(e.target as Node)) return;
      if (newPinDraft) closeNewPin();
      else if (activeAnnotationId) closeAnnotationPopover();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [newPinDraft, activeAnnotationId, closeNewPin, closeAnnotationPopover]);

  const handleImageLoad = useCallback(() => {
    recomputeRect();
  }, [recomputeRect]);

  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const target = e.target as HTMLElement;
      if (target.closest("[data-pin]") || target.closest("[data-annotation-popover]")) return;

      // A popover is open — a click anywhere else in the scene just closes it
      // (one action per click; a second click can then place/open a new one).
      if (newPinDraft) {
        closeNewPin();
        return;
      }
      if (activeAnnotationId) {
        closeAnnotationPopover();
        return;
      }

      if (!annotationMode || !containerRef.current || !onCanvasClick || !renderedRect) return;

      const rect = containerRef.current.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const clickY = e.clientY - rect.top;

      const { offsetX, offsetY, width, height } = renderedRect;
      // Ignore clicks that land in the object-fit:contain letterbox padding.
      if (
        clickX < offsetX ||
        clickX > offsetX + width ||
        clickY < offsetY ||
        clickY > offsetY + height ||
        width <= 0 ||
        height <= 0
      ) {
        return;
      }

      const xPercent = ((clickX - offsetX) / width) * 100;
      const yPercent = ((clickY - offsetY) / height) * 100;
      onCanvasClick(Math.min(100, Math.max(0, xPercent)), Math.min(100, Math.max(0, yPercent)));
    },
    [annotationMode, onCanvasClick, renderedRect, newPinDraft, activeAnnotationId, closeNewPin, closeAnnotationPopover],
  );

  const pinStyle = useCallback(
    (xPercent: number, yPercent: number): React.CSSProperties => {
      if (!renderedRect) {
        // Fall back to container-relative percent until the image has loaded.
        return { left: `${xPercent}%`, top: `${yPercent}%` };
      }
      const { offsetX, offsetY, width, height } = renderedRect;
      return {
        left: `${offsetX + (xPercent / 100) * width}px`,
        top: `${offsetY + (yPercent / 100) * height}px`,
      };
    },
    [renderedRect],
  );

  const anchorPxFor = useCallback(
    (xPercent: number, yPercent: number): { x: number; y: number } => {
      if (!renderedRect) return { x: (xPercent / 100) * containerSize.width, y: (yPercent / 100) * containerSize.height };
      const { offsetX, offsetY, width, height } = renderedRect;
      return { x: offsetX + (xPercent / 100) * width, y: offsetY + (yPercent / 100) * height };
    },
    [renderedRect, containerSize],
  );

  if (loading) {
    return (
      <div className={cn("flex items-center justify-center bg-surface-2 rounded-xl", className)}>
        <div className="flex flex-col items-center gap-2 text-text-muted">
          <svg className="w-6 h-6 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
          </svg>
          <span className="text-xs">{t("briefs.media.loading")}</span>
        </div>
      </div>
    );
  }

  if (!blobUrl) {
    return (
      <div className={cn("flex items-center justify-center bg-surface-2 rounded-xl", className)}>
        <p className="text-sm text-text-muted">{t("briefs.media.loadFailed")}</p>
      </div>
    );
  }

  const activeAnnotation = activeAnnotationId ? annotations.find((a) => a.id === activeAnnotationId) ?? null : null;

  return (
    <div
      ref={containerRef}
      className={cn(
        "relative select-none overflow-visible rounded-xl",
        annotationMode && "cursor-crosshair",
        className,
      )}
      onClick={handleClick}
      role={annotationMode ? "application" : undefined}
      aria-label={annotationMode ? t("briefs.annotation.canvasAria") : undefined}
    >
      <div className="absolute inset-0 overflow-hidden rounded-xl">
        <img
          ref={imgRef}
          src={blobUrl}
          alt="Deliverable"
          className="w-full h-full object-contain block"
          draggable={false}
          onLoad={handleImageLoad}
        />
      </div>

      {/* Annotation mode overlay */}
      {annotationMode && (
        <div className="absolute inset-0 bg-accent/5 border-2 border-accent/40 border-dashed rounded-xl pointer-events-none" />
      )}

      {/* Pins */}
      {annotations.map((ann) => {
        if (ann.x_percent == null || ann.y_percent == null) return null;
        const isActive = ann.id === activeAnnotationId;
        const isHovered = ann.id === hoverPin;
        const isResolved = ann.status === "resolved";
        const isPulsing = ann.id === pulseAnnotationId;
        const colorClass = isResolved
          ? "bg-surface-2 border-border text-text-muted"
          : (TYPE_COLORS[ann.annotation_type] ?? TYPE_COLORS.general);
        const preview = ann.body ? ann.body.slice(0, 80) : t("briefs.comments.revisionNote");
        const label = t("briefs.annotation.markerAria", {
          status: t(isResolved ? "briefs.annotation.resolved" : "briefs.annotation.open"),
          number: ann.label_number,
          preview,
        });

        return (
          <span key={ann.id} className="absolute" style={{ ...pinStyle(ann.x_percent, ann.y_percent), transform: "translate(-50%, -50%)" }}>
            {isPulsing && (
              <span className="absolute inset-0 -m-1.5 rounded-full bg-accent/50 motion-safe:animate-ping motion-reduce:hidden" aria-hidden="true" />
            )}
            <button
              ref={(el) => {
                if (el) markerButtonRefs.current.set(ann.id, el);
                else markerButtonRefs.current.delete(ann.id);
              }}
              data-pin="true"
              type="button"
              aria-label={label}
              title={label}
              aria-expanded={isActive}
              className={cn(
                "relative w-7 h-7 rounded-full border-2 shadow-lg",
                "flex items-center justify-center text-[11px] font-bold",
                "transition-all duration-150 motion-reduce:transition-none",
                "after:absolute after:-inset-2 after:content-['']", // enlarges touch target without changing visual size
                colorClass,
                (isActive || isHovered) && "scale-125 z-20 motion-reduce:scale-100",
                !isActive && !isHovered && "z-10",
                isResolved && "opacity-60",
              )}
              onMouseEnter={() => setHoverPin(ann.id)}
              onMouseLeave={() => setHoverPin(null)}
              onFocus={() => setHoverPin(ann.id)}
              onBlur={() => setHoverPin(null)}
              onClick={(e) => {
                e.stopPropagation();
                onAnnotationClick?.(ann);
              }}
            >
              {isResolved ? (
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                ann.label_number
              )}
            </button>
          </span>
        );
      })}

      {/* Pending new-pin marker */}
      {newPinDraft && (
        <span
          className="absolute w-7 h-7 rounded-full border-2 border-dashed border-amber-500 bg-white shadow-lg flex items-center justify-center text-[11px] font-bold text-amber-600 motion-safe:animate-pulse"
          style={{ ...pinStyle(newPinDraft.x, newPinDraft.y), transform: "translate(-50%, -50%)" }}
          aria-hidden="true"
        >
          +
        </span>
      )}

      {/* Annotation mode helper text */}
      {annotationMode && !newPinDraft && !activeAnnotationId && (
        <div className="absolute bottom-3 left-1/2 -translate-x-1/2 pointer-events-none">
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-black/70 text-white text-xs rounded-full backdrop-blur-sm">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
            </svg>
            {t("briefs.annotation.canvasHint")}
          </span>
        </div>
      )}

      {newPinDraft && renderNewPinComposer && (
        <PopoverBubble
          anchor={anchorPxFor(newPinDraft.x, newPinDraft.y)}
          containerSize={containerSize}
          compact={isMobile}
          onRequestClose={closeNewPin}
          ariaLabel={t("briefs.annotation.add")}
        >
          {renderNewPinComposer()}
        </PopoverBubble>
      )}

      {activeAnnotation && renderAnnotationPopover && (
        <PopoverBubble
          anchor={anchorPxFor(activeAnnotation.x_percent ?? 50, activeAnnotation.y_percent ?? 50)}
          containerSize={containerSize}
          compact={isMobile}
          onRequestClose={closeAnnotationPopover}
          ariaLabel={t("briefs.annotation.detailAria", { number: activeAnnotation.label_number })}
        >
          {renderAnnotationPopover(activeAnnotation)}
        </PopoverBubble>
      )}
    </div>
  );
}

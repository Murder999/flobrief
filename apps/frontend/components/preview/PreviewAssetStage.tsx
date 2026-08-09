"use client";

// Composes the EXISTING AnnotationCanvas (unchanged) inside platform chrome
// for the main, annotatable surface, or a lightweight thumbnail (no
// annotation affordance) for grid/carousel thumbnails. Never reimplements
// AnnotationCanvas's ResizeObserver/computeContainRect math — that's the
// whole point of this file.

import { useEffect, useState } from "react";
import type { AnnotationRead } from "@/lib/api-client";
import AnnotationCanvas from "@/components/media/AnnotationCanvas";
import { useAuthBlob } from "@/components/media/MediaPreview";
import type { SafeZoneRect } from "./previewPlatformConfig";
import { cn } from "@/lib/utils";

interface PreviewAssetStageProps {
  assetId: string | null;
  accessToken: string;
  /** width / height; 0 or undefined means no fixed ratio (fills container height). */
  aspectRatio?: number;
  /** Full annotatable surface (main preview) vs. a lightweight, non-interactive thumbnail. */
  mode: "annotatable" | "thumbnail";
  annotations?: AnnotationRead[];
  activeAnnotationId?: string | null;
  onAnnotationClick?: (annotation: AnnotationRead) => void;
  annotationMode?: boolean;
  onCanvasClick?: (x: number, y: number) => void;
  onExitAnnotationMode?: () => void;
  newPinDraft?: { x: number; y: number } | null;
  renderNewPinComposer?: () => React.ReactNode;
  onCloseNewPinComposer?: () => void;
  renderAnnotationPopover?: (annotation: AnnotationRead) => React.ReactNode;
  onCloseAnnotationPopover?: () => void;
  safeZones?: SafeZoneRect[];
  className?: string;
}

export function PreviewAssetStage({
  assetId,
  accessToken,
  aspectRatio,
  mode,
  annotations = [],
  activeAnnotationId,
  onAnnotationClick,
  annotationMode = false,
  onCanvasClick,
  onExitAnnotationMode,
  newPinDraft,
  renderNewPinComposer,
  onCloseNewPinComposer,
  renderAnnotationPopover,
  onCloseAnnotationPopover,
  safeZones,
  className,
}: PreviewAssetStageProps) {
  if (!assetId) {
    return (
      <div
        className={cn("flex items-center justify-center bg-surface-2", className)}
        style={aspectRatio ? { aspectRatio } : undefined}
      >
        <p className="text-xs text-text-muted">Görsel seçilmedi</p>
      </div>
    );
  }

  if (mode === "thumbnail") {
    return (
      <ThumbnailStage
        assetId={assetId}
        accessToken={accessToken}
        aspectRatio={aspectRatio}
        className={className}
      />
    );
  }

  return (
    <div
      className={cn("relative w-full bg-surface-2 overflow-hidden", className)}
      style={aspectRatio ? { aspectRatio } : undefined}
    >
      <AnnotationCanvas
        assetId={assetId}
        accessToken={accessToken}
        annotations={annotations}
        activeAnnotationId={activeAnnotationId}
        annotationMode={annotationMode}
        onCanvasClick={onCanvasClick}
        onAnnotationClick={onAnnotationClick}
        onExitAnnotationMode={onExitAnnotationMode}
        className="absolute inset-0 w-full h-full"
        newPinDraft={newPinDraft}
        renderNewPinComposer={renderNewPinComposer}
        onCloseNewPinComposer={onCloseNewPinComposer}
        renderAnnotationPopover={renderAnnotationPopover}
        onCloseAnnotationPopover={onCloseAnnotationPopover}
      />
      {safeZones?.map((zone, i) => (
        <div
          key={i}
          aria-hidden="true"
          className="pointer-events-none absolute border border-dashed border-white/50"
          style={{
            top: `${zone.top}%`,
            left: `${zone.left}%`,
            right: `${zone.right}%`,
            bottom: `${zone.bottom}%`,
          }}
          title={zone.label}
        />
      ))}
    </div>
  );
}

function ThumbnailStage({
  assetId,
  accessToken,
  aspectRatio,
  className,
}: {
  assetId: string;
  accessToken: string;
  aspectRatio?: number;
  className?: string;
}) {
  const { blobUrl, loading } = useAuthBlob(assetId, accessToken);
  const [errored, setErrored] = useState(false);

  useEffect(() => {
    setErrored(false);
  }, [assetId]);

  return (
    <div
      className={cn("relative w-full bg-surface-2 overflow-hidden", className)}
      style={aspectRatio ? { aspectRatio } : undefined}
    >
      {loading && <div className="absolute inset-0 animate-pulse bg-surface-2" />}
      {!loading && blobUrl && !errored && (
        <img
          src={blobUrl}
          alt=""
          className="absolute inset-0 w-full h-full object-cover"
          draggable={false}
          onError={() => setErrored(true)}
        />
      )}
      {!loading && (!blobUrl || errored) && (
        <div className="absolute inset-0 flex items-center justify-center text-text-muted text-[10px]">
          Görsel yok
        </div>
      )}
    </div>
  );
}

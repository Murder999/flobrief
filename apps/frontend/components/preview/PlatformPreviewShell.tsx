"use client";

// Outer chrome + dispatch to the matching per-platform renderer. Renders the
// "bu içerik türü için önizleme henüz desteklenmiyor" state whenever the
// platform x format combination isn't in previewPlatformConfig's map —
// never fakes a preview for an unsupported combination.

import { useEffect, useRef, useState } from "react";
import { AlertTriangle } from "lucide-react";
import type { AnnotationRead, PreviewConfigRead, PreviewSlotRead } from "@/lib/api-client";
import { getFormatConfig, PLATFORM_LABELS, FORMAT_LABELS } from "./previewPlatformConfig";
import InstagramFeedPreview from "./InstagramFeedPreview";
import InstagramStoryPreview from "./InstagramStoryPreview";
import InstagramGridPreview from "./InstagramGridPreview";
import FacebookPostPreview from "./FacebookPostPreview";
import LinkedInPostPreview from "./LinkedInPostPreview";
import XPostPreview from "./XPostPreview";
import TikTokPreview from "./TikTokPreview";
import type { PlatformPreviewProps } from "./previewTypes";

type Renderer = (props: PlatformPreviewProps) => React.ReactElement;

function resolveRenderer(platform: string, chrome: string): Renderer | null {
  if (platform === "instagram") {
    if (chrome === "feed") return InstagramFeedPreview;
    if (chrome === "story") return InstagramStoryPreview;
    if (chrome === "grid") return InstagramGridPreview;
    return null;
  }
  if (platform === "facebook") return FacebookPostPreview;
  if (platform === "linkedin") return LinkedInPostPreview;
  if (platform === "x") return XPostPreview;
  if (platform === "tiktok") return TikTokPreview;
  return null;
}

interface PlatformPreviewShellProps {
  config: PreviewConfigRead;
  slots: PreviewSlotRead[];
  accessToken: string;
  annotations: AnnotationRead[];
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
  readOnly?: boolean;
  onActiveAssetChange?: (assetId: string | null) => void;
}

export function PlatformPreviewShell({
  config,
  slots,
  accessToken,
  annotations,
  activeAnnotationId,
  onAnnotationClick,
  annotationMode,
  onCanvasClick,
  onExitAnnotationMode,
  newPinDraft,
  renderNewPinComposer,
  onCloseNewPinComposer,
  renderAnnotationPopover,
  onCloseAnnotationPopover,
  readOnly,
  onActiveAssetChange,
}: PlatformPreviewShellProps) {
  const [activeSlotIndex, setActiveSlotIndex] = useState(0);
  const touchStartX = useRef<number | null>(null);
  const SWIPE_THRESHOLD_PX = 40;

  const handleTouchStart = (e: React.TouchEvent) => {
    touchStartX.current = e.touches[0]?.clientX ?? null;
  };
  const handleTouchEnd = (e: React.TouchEvent) => {
    const startX = touchStartX.current;
    touchStartX.current = null;
    if (startX == null || slots.length <= 1) return;
    const endX = e.changedTouches[0]?.clientX ?? startX;
    const delta = endX - startX;
    if (Math.abs(delta) < SWIPE_THRESHOLD_PX) return;
    setActiveSlotIndex((i) => {
      const next = delta < 0 ? i + 1 : i - 1;
      return Math.max(0, Math.min(next, slots.length - 1));
    });
  };

  useEffect(() => {
    setActiveSlotIndex(0);
  }, [config.deliverable_id]);

  useEffect(() => {
    if (activeSlotIndex >= slots.length && slots.length > 0) setActiveSlotIndex(0);
  }, [slots.length, activeSlotIndex]);

  useEffect(() => {
    onActiveAssetChange?.(slots[activeSlotIndex]?.asset_id ?? null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSlotIndex, slots]);

  const formatConfig = getFormatConfig(config.platform, config.preview_format);

  if (!formatConfig) {
    return (
      <div className="mx-auto w-full max-w-[420px] rounded-xl border border-dashed border-border bg-surface-2 p-8 text-center">
        <AlertTriangle className="w-6 h-6 text-text-muted mx-auto mb-2" />
        <p className="text-sm font-medium text-text">
          {PLATFORM_LABELS[config.platform] ?? config.platform} · {FORMAT_LABELS[config.preview_format] ?? config.preview_format}
        </p>
        <p className="text-xs text-text-muted mt-1">
          Bu içerik türü için önizleme henüz desteklenmiyor.
        </p>
      </div>
    );
  }

  const activeAssetId = slots[activeSlotIndex]?.asset_id ?? null;
  const scopedAnnotations = annotations.filter((a) => a.asset_id === activeAssetId || a.asset_id === null);

  const Renderer = resolveRenderer(config.platform, formatConfig.chrome);
  if (!Renderer) {
    return (
      <div className="mx-auto w-full max-w-[420px] rounded-xl border border-dashed border-border bg-surface-2 p-8 text-center">
        <AlertTriangle className="w-6 h-6 text-text-muted mx-auto mb-2" />
        <p className="text-sm text-text-muted">Bu içerik türü için önizleme henüz desteklenmiyor.</p>
      </div>
    );
  }

  const canSwipe = slots.length > 1 && !annotationMode;

  return (
    <div
      onTouchStart={canSwipe ? handleTouchStart : undefined}
      onTouchEnd={canSwipe ? handleTouchEnd : undefined}
    >
      <Renderer
        config={config}
        formatConfig={formatConfig}
        slots={slots}
        activeSlotIndex={activeSlotIndex}
        onSelectSlot={setActiveSlotIndex}
        accessToken={accessToken}
        annotations={readOnly ? [] : scopedAnnotations}
        activeAnnotationId={activeAnnotationId}
        onAnnotationClick={onAnnotationClick}
        annotationMode={annotationMode}
        onCanvasClick={onCanvasClick}
        onExitAnnotationMode={onExitAnnotationMode}
        newPinDraft={newPinDraft}
        renderNewPinComposer={renderNewPinComposer}
        onCloseNewPinComposer={onCloseNewPinComposer}
        renderAnnotationPopover={renderAnnotationPopover}
        onCloseAnnotationPopover={onCloseAnnotationPopover}
        readOnly={readOnly}
      />
    </div>
  );
}

// Shared prop contract for every per-platform preview renderer
// (InstagramFeedPreview, FacebookPostPreview, ...). Each renderer is a pure
// presentational component: it receives config/slots/format chrome already
// resolved by PlatformPreviewShell and does zero platform-detection
// branching of its own.

import type { AnnotationRead, PreviewConfigRead, PreviewSlotRead } from "@/lib/api-client";
import type { PlatformFormatConfig } from "./previewPlatformConfig";

export interface PlatformPreviewProps {
  config: PreviewConfigRead;
  formatConfig: PlatformFormatConfig;
  slots: PreviewSlotRead[];
  activeSlotIndex: number;
  onSelectSlot: (index: number) => void;
  accessToken: string;
  /** Annotations already filtered to the currently active slide's asset_id. */
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
  /** True when viewing a past version snapshot — no annotation affordance offered. */
  readOnly?: boolean;
}

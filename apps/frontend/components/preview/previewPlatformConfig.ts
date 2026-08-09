// Single source of truth for the Social Media Preview Center's platform x
// format chrome: aspect ratio, safe-zone rects (same 0–100% coordinate space
// AnnotationCanvas already uses), caption truncation length, and which
// "chrome" (feed/story/grid/document/text) a combination renders with.
//
// This mirrors the backend's `_PLATFORM_FORMATS` map in
// app/schemas/deliverable_preview.py — a combination unsupported here must
// also be unsupported there, and vice versa. PlatformPreviewShell.tsx
// consults this file, never a component's own branching, to decide whether
// a combination is renderable at all.

import type { PreviewFormat, PreviewPlatform } from "@/lib/api-client";

export type PreviewChrome = "feed" | "story" | "grid" | "document" | "text";

export interface SafeZoneRect {
  /** 0–100, image-relative percent, same space as AnnotationCanvas coordinates. */
  top: number;
  left: number;
  right: number;
  bottom: number;
  label: string;
}

export interface PlatformFormatConfig {
  /** width / height */
  aspectRatio: number;
  captionTruncateAt: number;
  chrome: PreviewChrome;
  safeZones?: SafeZoneRect[];
  formatLabel: string;
}

export const PLATFORM_LABELS: Record<PreviewPlatform, string> = {
  instagram: "Instagram",
  facebook: "Facebook",
  tiktok: "TikTok",
  linkedin: "LinkedIn",
  x: "X",
};

export const FORMAT_LABELS: Record<PreviewFormat, string> = {
  feed_single: "Akış (Tekli)",
  feed_carousel: "Akış (Karusel)",
  story: "Hikaye",
  reel: "Reels",
  reel_cover: "Reels Kapağı",
  grid: "Izgara",
  document_carousel: "Belge Karuseli",
  text_post: "Metin Gönderisi",
};

const STORY_SAFE_ZONES: SafeZoneRect[] = [
  { top: 0, left: 0, right: 100, bottom: 12, label: "Üst güvenli alan" },
  { top: 88, left: 0, right: 100, bottom: 0, label: "Alt güvenli alan (yanıt çubuğu)" },
];

// Platform -> format -> chrome config. Only combinations present here are
// ever rendered — an absent entry means PlatformPreviewShell falls back to
// the "desteklenmiyor" state instead of faking a preview.
export const PLATFORM_FORMATS: Partial<
  Record<PreviewPlatform, Partial<Record<PreviewFormat, PlatformFormatConfig>>>
> = {
  instagram: {
    feed_single: { aspectRatio: 1, captionTruncateAt: 125, chrome: "feed", formatLabel: FORMAT_LABELS.feed_single },
    feed_carousel: { aspectRatio: 1, captionTruncateAt: 125, chrome: "feed", formatLabel: FORMAT_LABELS.feed_carousel },
    story: { aspectRatio: 9 / 16, captionTruncateAt: 0, chrome: "story", safeZones: STORY_SAFE_ZONES, formatLabel: FORMAT_LABELS.story },
    reel: { aspectRatio: 9 / 16, captionTruncateAt: 125, chrome: "story", safeZones: STORY_SAFE_ZONES, formatLabel: FORMAT_LABELS.reel },
    reel_cover: { aspectRatio: 9 / 16, captionTruncateAt: 0, chrome: "story", formatLabel: FORMAT_LABELS.reel_cover },
    grid: { aspectRatio: 1, captionTruncateAt: 0, chrome: "grid", formatLabel: FORMAT_LABELS.grid },
  },
  facebook: {
    feed_single: { aspectRatio: 1.91, captionTruncateAt: 477, chrome: "feed", formatLabel: FORMAT_LABELS.feed_single },
    feed_carousel: { aspectRatio: 1.91, captionTruncateAt: 477, chrome: "feed", formatLabel: FORMAT_LABELS.feed_carousel },
    story: { aspectRatio: 9 / 16, captionTruncateAt: 0, chrome: "story", safeZones: STORY_SAFE_ZONES, formatLabel: FORMAT_LABELS.story },
  },
  linkedin: {
    feed_single: { aspectRatio: 1.91, captionTruncateAt: 210, chrome: "feed", formatLabel: FORMAT_LABELS.feed_single },
    feed_carousel: { aspectRatio: 1, captionTruncateAt: 210, chrome: "feed", formatLabel: FORMAT_LABELS.feed_carousel },
    document_carousel: { aspectRatio: 0.77, captionTruncateAt: 210, chrome: "document", formatLabel: FORMAT_LABELS.document_carousel },
    text_post: { aspectRatio: 0, captionTruncateAt: 210, chrome: "text", formatLabel: FORMAT_LABELS.text_post },
  },
  x: {
    feed_single: { aspectRatio: 1.78, captionTruncateAt: 280, chrome: "feed", formatLabel: FORMAT_LABELS.feed_single },
    feed_carousel: { aspectRatio: 1.78, captionTruncateAt: 280, chrome: "feed", formatLabel: FORMAT_LABELS.feed_carousel },
    text_post: { aspectRatio: 0, captionTruncateAt: 280, chrome: "text", formatLabel: FORMAT_LABELS.text_post },
  },
  tiktok: {
    reel: { aspectRatio: 9 / 16, captionTruncateAt: 150, chrome: "story", safeZones: STORY_SAFE_ZONES, formatLabel: FORMAT_LABELS.reel },
    reel_cover: { aspectRatio: 9 / 16, captionTruncateAt: 0, chrome: "story", formatLabel: FORMAT_LABELS.reel_cover },
  },
};

export function getFormatConfig(
  platform: PreviewPlatform,
  format: PreviewFormat,
): PlatformFormatConfig | null {
  return PLATFORM_FORMATS[platform]?.[format] ?? null;
}

export function isSupportedCombo(platform: PreviewPlatform, format: PreviewFormat): boolean {
  return getFormatConfig(platform, format) !== null;
}

export function formatsForPlatform(platform: PreviewPlatform): PreviewFormat[] {
  return Object.keys(PLATFORM_FORMATS[platform] ?? {}) as PreviewFormat[];
}

export const ALL_PREVIEW_PLATFORMS: PreviewPlatform[] = ["instagram", "facebook", "linkedin", "x", "tiktok"];

export function truncateCaption(caption: string | null, format: PlatformFormatConfig): {
  text: string;
  truncated: boolean;
} {
  if (!caption) return { text: "", truncated: false };
  if (!format.captionTruncateAt || caption.length <= format.captionTruncateAt) {
    return { text: caption, truncated: false };
  }
  return { text: caption.slice(0, format.captionTruncateAt).trimEnd() + "…", truncated: true };
}

"use client";

// Agency-only editing surface: platform/format picker, caption + hashtags,
// and (for carousel-shaped formats) the slide-order editor. Caption/hashtag
// edits autosave via usePreviewDraftState's debounce (never one request per
// keystroke); carousel reorders and the platform/format picker save
// immediately since those are discrete actions, not free text typing.

import { useMemo, useState } from "react";
import {
  deliverablePreviewApi,
  type AssetRead,
  type PreviewConfigRead,
  type PreviewConfigUpsert,
  type PreviewFormat,
  type PreviewPlatform,
  type PreviewSlotRead,
} from "@/lib/api-client";
import { PreviewPlatformSwitcher } from "./PreviewPlatformSwitcher";
import { PreviewCarouselEditor, type CarouselSlotDraft } from "./PreviewCarouselEditor";
import { usePreviewDraftState } from "./usePreviewDraftState";

const CAROUSEL_FORMATS = new Set<PreviewFormat>(["feed_carousel", "grid", "document_carousel"]);

interface PreviewConfigEditorProps {
  briefId: string;
  deliverableId: string;
  agencyId: string;
  accessToken: string;
  /** Assets already linked to this deliverable — candidates for carousel slots. */
  assets: AssetRead[];
  config: PreviewConfigRead | null;
  slots: PreviewSlotRead[];
  onConfigSaved: (config: PreviewConfigRead) => void;
  onSlotsSaved: (slots: PreviewSlotRead[]) => void;
}

interface DraftFields {
  platform: PreviewPlatform;
  preview_format: PreviewFormat;
  caption: string;
  hashtags: string;
}

export function PreviewConfigEditor({
  briefId,
  deliverableId,
  agencyId,
  accessToken,
  assets,
  config,
  slots,
  onConfigSaved,
  onSlotsSaved,
}: PreviewConfigEditorProps) {
  const initial = useMemo<DraftFields>(
    () => ({
      platform: config?.platform ?? "instagram",
      preview_format: config?.preview_format ?? "feed_single",
      caption: config?.caption ?? "",
      hashtags: (config?.hashtags ?? []).join(", "),
    }),
    [config?.platform, config?.preview_format, config?.caption, config?.hashtags],
  );

  const { draft, update, saving, error, saveNow } = usePreviewDraftState<DraftFields>({
    initial,
    onSave: async (value) => {
      const payload: PreviewConfigUpsert = {
        platform: value.platform,
        preview_format: value.preview_format,
        caption: value.caption.trim() ? value.caption : null,
        hashtags: value.hashtags.trim()
          ? value.hashtags.split(",").map((h) => h.trim()).filter(Boolean)
          : null,
      };
      const saved = await deliverablePreviewApi.upsertConfig(
        briefId, deliverableId, payload, accessToken, agencyId,
      );
      onConfigSaved(saved);
    },
  });

  const isCarousel = CAROUSEL_FORMATS.has(draft.preview_format);
  const [savingSlots, setSavingSlots] = useState(false);

  const carouselDrafts: CarouselSlotDraft[] = useMemo(() => {
    if (slots.length > 0) {
      return slots.map((s) => ({ asset_id: s.asset_id, position: s.position, is_cover: s.is_cover }));
    }
    return assets.map((a, i) => ({ asset_id: a.id, position: i, is_cover: i === 0 }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slots, assets]);

  const handleSlotsChange = async (next: CarouselSlotDraft[]) => {
    setSavingSlots(true);
    try {
      const saved = await deliverablePreviewApi.reorderSlots(
        briefId,
        deliverableId,
        { slots: next.map((s) => ({ asset_id: s.asset_id, position: s.position, is_cover: s.is_cover })) },
        accessToken,
        agencyId,
      );
      onSlotsSaved(saved);
    } finally {
      setSavingSlots(false);
    }
  };

  return (
    <div className="space-y-3 rounded-xl border border-border bg-surface-2 p-3.5">
      <PreviewPlatformSwitcher
        platform={draft.platform}
        format={draft.preview_format}
        onChange={(platform, preview_format) => {
          update({ platform, preview_format });
        }}
      />

      <div>
        <label htmlFor="preview-caption" className="block text-[11px] font-medium text-text-muted mb-1">
          Başlık / Açıklama
        </label>
        <textarea
          id="preview-caption"
          value={draft.caption}
          onChange={(e) => update({ caption: e.target.value })}
          rows={3}
          placeholder="Gönderi metnini yazın…"
          className="w-full px-3 py-2 text-xs bg-surface border border-border rounded-lg resize-none focus:outline-none focus:border-accent text-text placeholder:text-text-muted"
        />
      </div>

      <div>
        <label htmlFor="preview-hashtags" className="block text-[11px] font-medium text-text-muted mb-1">
          Hashtag&apos;ler (virgülle ayırın)
        </label>
        <input
          id="preview-hashtags"
          type="text"
          value={draft.hashtags}
          onChange={(e) => update({ hashtags: e.target.value })}
          placeholder="#kampanya, #yenisezon"
          className="w-full px-3 py-2 text-xs bg-surface border border-border rounded-lg focus:outline-none focus:border-accent text-text placeholder:text-text-muted"
        />
      </div>

      {isCarousel && assets.length > 0 && (
        <PreviewCarouselEditor
          slots={carouselDrafts}
          onChange={handleSlotsChange}
          accessToken={accessToken}
          disabled={savingSlots}
        />
      )}

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => void saveNow()}
          disabled={saving}
          className="px-3 py-1.5 text-[11px] font-semibold text-white bg-accent hover:bg-accent/90 rounded-lg disabled:opacity-50 transition-colors"
        >
          {saving ? "Kaydediliyor…" : "Şimdi Kaydet"}
        </button>
        <span className="text-[11px] text-text-muted">
          {saving ? "Kaydediliyor…" : error ? <span className="text-red-500">{error}</span> : "Değişiklikler otomatik kaydedilir"}
        </span>
      </div>
    </div>
  );
}

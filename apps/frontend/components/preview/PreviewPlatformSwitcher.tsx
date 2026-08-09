"use client";

import type { PreviewFormat, PreviewPlatform } from "@/lib/api-client";
import { ALL_PREVIEW_PLATFORMS, PLATFORM_LABELS, FORMAT_LABELS, formatsForPlatform } from "./previewPlatformConfig";
import { cn } from "@/lib/utils";

interface PreviewPlatformSwitcherProps {
  platform: PreviewPlatform;
  format: PreviewFormat;
  onChange: (platform: PreviewPlatform, format: PreviewFormat) => void;
  disabled?: boolean;
}

/** Platform + format pickers, constrained to backend-validated combinations
 * only (via previewPlatformConfig.formatsForPlatform) — never offers a
 * combination the API would reject. */
export function PreviewPlatformSwitcher({ platform, format, onChange, disabled }: PreviewPlatformSwitcherProps) {
  const availableFormats = formatsForPlatform(platform);

  const handlePlatformChange = (next: PreviewPlatform) => {
    const nextFormats = formatsForPlatform(next);
    const nextFormat = nextFormats.includes(format) ? format : nextFormats[0];
    onChange(next, nextFormat);
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Platform seçimi">
        {ALL_PREVIEW_PLATFORMS.map((p) => (
          <button
            key={p}
            type="button"
            disabled={disabled}
            onClick={() => handlePlatformChange(p)}
            aria-pressed={p === platform}
            className={cn(
              "px-2.5 py-1.5 rounded-lg text-[12px] font-medium border transition-colors disabled:opacity-50",
              p === platform
                ? "bg-accent text-white border-accent"
                : "bg-surface text-text-muted border-border hover:border-accent/40",
            )}
          >
            {PLATFORM_LABELS[p]}
          </button>
        ))}
      </div>

      <select
        aria-label="Önizleme formatı"
        value={format}
        disabled={disabled}
        onChange={(e) => onChange(platform, e.target.value as PreviewFormat)}
        className="px-2.5 py-1.5 rounded-lg text-[12px] font-medium border border-border bg-surface text-text disabled:opacity-50"
      >
        {availableFormats.map((f) => (
          <option key={f} value={f}>
            {FORMAT_LABELS[f]}
          </option>
        ))}
      </select>
    </div>
  );
}

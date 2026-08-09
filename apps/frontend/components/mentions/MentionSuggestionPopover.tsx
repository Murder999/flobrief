"use client";

import { createPortal } from "react-dom";
import type { MentionCandidate } from "@/lib/api-client";
import type { MentionTriggerState } from "./useMentionTrigger";

interface MentionSuggestionPopoverProps {
  state: MentionTriggerState;
  onSelect: (candidate: MentionCandidate) => void;
  onHighlight: (index: number) => void;
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  const first = parts[0]?.[0] ?? "?";
  const last = parts.length > 1 ? parts[parts.length - 1]?.[0] ?? "" : "";
  return (first + last).toUpperCase();
}

/**
 * Body-portal popover so it's never clipped by a modal/drawer's overflow
 * (§D). Position is caller-computed (caret rect), clamped to the viewport
 * here so it never runs off-screen on small screens.
 */
export function MentionSuggestionPopover({
  state,
  onSelect,
  onHighlight,
}: MentionSuggestionPopoverProps) {
  if (!state.active || !state.position || typeof document === "undefined") return null;

  // visualViewport shrinks when the on-screen keyboard opens on mobile;
  // window.innerHeight does not, so clamping against innerHeight alone would
  // let the popover render underneath the keyboard.
  const viewportWidth = window.visualViewport?.width ?? window.innerWidth;
  const viewportHeight = window.visualViewport?.height ?? window.innerHeight;
  const width = 280;
  const maxHeight = 260;

  let left = state.position.left;
  let top = state.position.top + 22;
  if (left + width > viewportWidth - 12) left = viewportWidth - width - 12;
  if (left < 12) left = 12;
  if (top + maxHeight > viewportHeight - 12) {
    top = state.position.top - maxHeight - 6;
  }
  if (top < 12) top = 12;

  return createPortal(
    <div
      role="listbox"
      aria-label="Bahsedilecek kişiler"
      className="fixed z-[100] w-[280px] max-h-[260px] overflow-y-auto rounded-xl border border-border bg-surface shadow-2xl py-1.5 animate-in fade-in slide-in-from-top-1 duration-100"
      style={{ top, left }}
    >
      {state.loading && (
        <div className="px-3 py-4 space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex items-center gap-2 animate-pulse">
              <div className="w-6 h-6 rounded-full bg-surface-2 flex-shrink-0" />
              <div className="h-2.5 flex-1 bg-surface-2 rounded" />
            </div>
          ))}
        </div>
      )}

      {!state.loading && state.error && (
        <p className="px-3 py-3 text-xs text-danger">{state.error}</p>
      )}

      {!state.loading && !state.error && state.candidates.length === 0 && (
        <p className="px-3 py-3 text-xs text-text-muted">
          &ldquo;{state.query}&rdquo; ile eşleşen kimse bulunamadı.
        </p>
      )}

      {!state.loading &&
        !state.error &&
        state.candidates.map((c, i) => (
          <button
            key={c.user_id}
            type="button"
            role="option"
            aria-selected={i === state.highlightedIndex}
            onMouseDown={(e) => {
              // mousedown (not click) so the editor's blur/selection isn't
              // lost before onSelect runs.
              e.preventDefault();
              onSelect(c);
            }}
            onMouseEnter={() => onHighlight(i)}
            className={`w-full flex items-center gap-2.5 px-3 py-2 text-left transition-colors ${
              i === state.highlightedIndex ? "bg-accent/10" : "hover:bg-hover"
            }`}
          >
            <div className="w-6 h-6 rounded-full bg-gradient-to-br from-violet-500 to-blue-500 text-white text-[10px] font-bold flex items-center justify-center flex-shrink-0 overflow-hidden">
              {c.avatar_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={c.avatar_url} alt="" className="w-full h-full object-cover" />
              ) : (
                initials(c.display_name)
              )}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium text-text truncate">{c.display_name}</p>
              <p className="text-[10px] text-text-muted truncate">
                {c.role_label}
                {c.context_label ? ` · ${c.context_label}` : ""}
              </p>
            </div>
          </button>
        ))}
    </div>,
    document.body
  );
}

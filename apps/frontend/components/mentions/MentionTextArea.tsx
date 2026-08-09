"use client";

import { useCallback, useRef } from "react";
import type { MentionCandidate } from "@/lib/api-client";
import { useMentionTrigger, detectTrigger } from "@/components/mentions/useMentionTrigger";
import { MentionSuggestionPopover } from "@/components/mentions/MentionSuggestionPopover";

interface MentionTextAreaProps {
  value: string;
  onChange: (v: string) => void;
  mentionCandidatesFetcher?: (query: string) => Promise<MentionCandidate[]>;
  onMentionInsert?: (candidate: MentionCandidate) => void;
  /** Presence renders a <textarea>; omit for a single-line <input>. */
  rows?: number;
  placeholder?: string;
  className?: string;
  maxLength?: number;
  autoFocus?: boolean;
  "aria-label"?: string;
  disabled?: boolean;
  /** Enter (reply rows) or Ctrl/Cmd+Enter (multi-line composer) triggers submit — ignored while the mention popover owns Enter/Tab. */
  submitOn?: "enter" | "mod-enter";
  onSubmitShortcut?: () => void;
}

/**
 * Lightweight, reusable @mention-aware plain-text field — shares the same
 * trigger-detection/popover/candidate-fetch pipeline as RichTextEditor, but
 * targets a native <textarea>/<input> (no contentEditable, no toolbar) for
 * compact surfaces like the annotation composer/reply row, where a full rich
 * text toolbar would be out of place. Mentions are inserted as plain
 * "@DisplayName " text, satisfying the backend's anti-spoofing check
 * (mentioned name literally present in the submitted body) with no separate
 * HTML representation to keep in sync.
 */
export function MentionTextArea({
  value,
  onChange,
  mentionCandidatesFetcher,
  onMentionInsert,
  rows,
  placeholder,
  className,
  maxLength,
  autoFocus,
  "aria-label": ariaLabel,
  disabled,
  submitOn,
  onSubmitShortcut,
}: MentionTextAreaProps) {
  const elRef = useRef<HTMLTextAreaElement & HTMLInputElement>(null);
  const mention = useMentionTrigger(mentionCandidatesFetcher);

  const detectAt = useCallback(
    (el: HTMLTextAreaElement | HTMLInputElement) => {
      if (!mentionCandidatesFetcher) return;
      const caret = el.selectionStart ?? el.value.length;
      const query = detectTrigger(el.value.slice(0, caret));
      if (query !== null) {
        const rect = el.getBoundingClientRect();
        mention.open(query, { top: rect.bottom, left: rect.left });
      } else {
        mention.close();
      }
    },
    [mentionCandidatesFetcher, mention]
  );

  const handleMentionSelect = useCallback(
    (candidate: MentionCandidate) => {
      const el = elRef.current;
      if (el) {
        const caret = el.selectionStart ?? value.length;
        const query = detectTrigger(value.slice(0, caret)) ?? "";
        const startOffset = caret - (query.length + 1); // +1 for "@"
        if (startOffset >= 0) {
          const before = value.slice(0, startOffset);
          const after = value.slice(caret);
          const insertion = `@${candidate.display_name} `;
          const newCaret = before.length + insertion.length;
          onChange(before + insertion + after);
          requestAnimationFrame(() => {
            el.focus();
            el.setSelectionRange(newCaret, newCaret);
          });
        }
      }
      mention.close();
      onMentionInsert?.(candidate);
    },
    [value, onChange, onMentionInsert, mention]
  );

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement | HTMLInputElement>) => {
    onChange(e.target.value);
    detectAt(e.target);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement | HTMLInputElement>) => {
    if (mention.state.active) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        mention.moveHighlight(1);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        mention.moveHighlight(-1);
        return;
      }
      if (e.key === "Enter" || e.key === "Tab") {
        if (mention.state.candidates.length > 0) {
          e.preventDefault();
          handleMentionSelect(mention.state.candidates[mention.state.highlightedIndex]);
          return;
        }
      }
      if (e.key === "Escape") {
        e.preventDefault();
        mention.close();
        return;
      }
    }

    if (onSubmitShortcut) {
      if (submitOn === "mod-enter" && (e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        onSubmitShortcut();
      } else if (submitOn === "enter" && e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        onSubmitShortcut();
      }
    }
  };

  const sharedProps = {
    ref: elRef,
    value,
    onChange: handleChange,
    onKeyDown: handleKeyDown,
    onBlur: () => mention.close(),
    placeholder,
    className,
    maxLength,
    autoFocus,
    disabled,
    "aria-label": ariaLabel,
  } as const;

  return (
    <>
      {rows ? <textarea {...sharedProps} rows={rows} /> : <input type="text" {...sharedProps} />}
      {mentionCandidatesFetcher && (
        <MentionSuggestionPopover state={mention.state} onSelect={handleMentionSelect} onHighlight={mention.setHighlight} />
      )}
    </>
  );
}

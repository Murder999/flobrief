"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { MentionCandidate } from "@/lib/api-client";

const TRIGGER_RE = /@([^\s@]{0,40})$/;
const DEBOUNCE_MS = 200;
const MAX_RESULTS = 20;

export interface MentionTriggerState {
  active: boolean;
  query: string;
  position: { top: number; left: number } | null;
  candidates: MentionCandidate[];
  loading: boolean;
  error: string | null;
  highlightedIndex: number;
}

const CLOSED_STATE: MentionTriggerState = {
  active: false,
  query: "",
  position: null,
  candidates: [],
  loading: false,
  error: null,
  highlightedIndex: 0,
};

/**
 * Detects an in-progress "@query" trigger from a text snippet + caret
 * position, independent of whether the host is a <textarea> or a
 * contentEditable node — callers extract "text before caret" their own way
 * and hand it to `detectTrigger`.
 */
export function detectTrigger(textBeforeCaret: string): string | null {
  const match = TRIGGER_RE.exec(textBeforeCaret);
  return match ? match[1] : null;
}

/**
 * Shared mention-popover state machine: trigger text → debounced candidate
 * fetch → keyboard navigation → selection. Insertion into the host editor
 * (contentEditable span vs plain-text splice) is the caller's job — this
 * hook only owns "what should the popover show right now".
 */
export function useMentionTrigger(
  fetchCandidates?: (query: string) => Promise<MentionCandidate[]>
) {
  const [state, setState] = useState<MentionTriggerState>(CLOSED_STATE);
  const requestIdRef = useRef(0);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const open = useCallback(
    (query: string, position: { top: number; left: number }) => {
      setState((prev) => ({
        ...prev,
        active: true,
        query,
        position,
        highlightedIndex: 0,
      }));

      if (!fetchCandidates) return;
      if (debounceRef.current) clearTimeout(debounceRef.current);
      const thisRequest = ++requestIdRef.current;
      setState((prev) => ({ ...prev, loading: true, error: null }));
      debounceRef.current = setTimeout(async () => {
        try {
          const results = await fetchCandidates(query);
          if (requestIdRef.current !== thisRequest) return; // stale response
          setState((prev) => ({
            ...prev,
            loading: false,
            candidates: results.slice(0, MAX_RESULTS),
            highlightedIndex: 0,
          }));
        } catch {
          if (requestIdRef.current !== thisRequest) return;
          setState((prev) => ({
            ...prev,
            loading: false,
            error: "Öneriler yüklenemedi.",
            candidates: [],
          }));
        }
      }, DEBOUNCE_MS);
    },
    [fetchCandidates]
  );

  const close = useCallback(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    requestIdRef.current++;
    setState(CLOSED_STATE);
  }, []);

  const moveHighlight = useCallback((delta: number) => {
    setState((prev) => {
      if (prev.candidates.length === 0) return prev;
      const next =
        (prev.highlightedIndex + delta + prev.candidates.length) % prev.candidates.length;
      return { ...prev, highlightedIndex: next };
    });
  }, []);

  const setHighlight = useCallback((index: number) => {
    setState((prev) => ({ ...prev, highlightedIndex: index }));
  }, []);

  useEffect(
    () => () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    },
    []
  );

  return { state, open, close, moveHighlight, setHighlight };
}

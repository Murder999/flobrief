"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const DEFAULT_AUTOSAVE_DELAY_MS = 1500;

interface UsePreviewDraftStateOptions<T> {
  initial: T;
  onSave: (value: T) => Promise<void>;
  autosaveDelayMs?: number;
}

interface UsePreviewDraftStateResult<T> {
  draft: T;
  /** Merge a partial patch (or a full replacement via updater fn) into the
   * draft. Never fires a network request itself — only schedules the
   * debounced autosave timer. */
  update: (patch: Partial<T> | ((prev: T) => T)) => void;
  dirty: boolean;
  saving: boolean;
  error: string | null;
  /** Explicit save — flushes immediately, bypassing the debounce timer. */
  saveNow: () => Promise<void>;
}

/** Local dirty-flag/autosave hook for preview config editing. `save()` only
 * ever fires on an explicit call or after the debounce window elapses with
 * no further edits — it is never triggered directly by a keystroke handler,
 * so typing in a caption field never fires one request per character. */
export function usePreviewDraftState<T>({
  initial,
  onSave,
  autosaveDelayMs = DEFAULT_AUTOSAVE_DELAY_MS,
}: UsePreviewDraftStateOptions<T>): UsePreviewDraftStateResult<T> {
  const [draft, setDraft] = useState<T>(initial);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const draftRef = useRef<T>(initial);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const savingRef = useRef(false);

  useEffect(() => {
    draftRef.current = initial;
    setDraft(initial);
    setDirty(false);
    if (timerRef.current) clearTimeout(timerRef.current);
  }, [initial]);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const flush = useCallback(async () => {
    if (savingRef.current) return;
    savingRef.current = true;
    setSaving(true);
    setError(null);
    try {
      await onSave(draftRef.current);
      setDirty(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Kaydedilemedi");
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onSave]);

  const saveNow = useCallback(async () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    await flush();
  }, [flush]);

  const update = useCallback(
    (patch: Partial<T> | ((prev: T) => T)) => {
      setDraft((prev) => {
        const next = typeof patch === "function" ? (patch as (p: T) => T)(prev) : { ...prev, ...patch };
        draftRef.current = next;
        return next;
      });
      setDirty(true);
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        timerRef.current = null;
        void flush();
      }, autosaveDelayMs);
    },
    [autosaveDelayMs, flush],
  );

  return { draft, update, dirty, saving, error, saveNow };
}

"use client";

import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { timeEntryApi, type ActiveTimerRead } from "@/lib/api-client";
import { Clock } from "lucide-react";
import { useEffect, useId, useRef, useState, useCallback } from "react";
import { createPortal } from "react-dom";
import { ManualEntryModal } from "./ManualEntryModal";
import { TimerControls } from "./TimerControls";
import { emitTimerChanged, onTimerChanged } from "@/lib/timer-events";

const PANEL_WIDTH = 280;
const VIEWPORT_MARGIN = 8;
const POLL_INTERVAL_MS = 30_000;

function formatBadgeElapsed(startedAtIso: string, nowMs: number): string {
  const elapsedMs = Math.max(0, nowMs - new Date(startedAtIso).getTime());
  const totalSeconds = Math.floor(elapsedMs / 1000);
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

/** Compact icon + mm:ss badge in the sidebar logo row, expanding to a
 * popover with full timer controls on click. Polls the server's active
 * timer on mount/interval — the ticking display is always recomputed from
 * the server's `started_at`, never a client-only interval alone. */
export function GlobalTimerWidget() {
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();
  const agencyId = activeAgency?.id ?? null;

  const [activeTimer, setActiveTimer] = useState<ActiveTimerRead | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [manualModalOpen, setManualModalOpen] = useState(false);
  const [panelPos, setPanelPos] = useState<{ top: number; left: number } | null>(null);
  const [mounted, setMounted] = useState(false);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const panelId = useId();

  const refreshActive = useCallback(async () => {
    if (!accessToken || !agencyId) return;
    try {
      const active = await timeEntryApi.getActive(agencyId, accessToken);
      setActiveTimer(active);
    } catch {
      /* silent — badge just stays in its last known state */
    }
  }, [accessToken, agencyId]);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    refreshActive();
    const interval = setInterval(refreshActive, POLL_INTERVAL_MS);
    const unsubscribe = onTimerChanged(refreshActive);
    return () => {
      clearInterval(interval);
      unsubscribe();
    };
  }, [refreshActive]);

  useEffect(() => {
    if (!activeTimer) return;
    const interval = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(interval);
  }, [activeTimer]);

  const computePosition = () => {
    const btn = buttonRef.current;
    if (!btn) return;
    const rect = btn.getBoundingClientRect();
    const left = Math.min(
      Math.max(VIEWPORT_MARGIN, rect.left),
      window.innerWidth - PANEL_WIDTH - VIEWPORT_MARGIN
    );
    setPanelPos({ top: rect.bottom + 8, left });
  };

  const toggleOpen = () => {
    setIsOpen((v) => {
      const next = !v;
      if (next) computePosition();
      return next;
    });
  };

  useEffect(() => {
    if (!isOpen) return;
    const handleClick = (e: MouseEvent) => {
      const target = e.target as Node;
      if (buttonRef.current?.contains(target) || panelRef.current?.contains(target)) return;
      setIsOpen(false);
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setIsOpen(false);
    };
    const handleScrollOrResize = () => setIsOpen(false);
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKeyDown);
    window.addEventListener("scroll", handleScrollOrResize, true);
    window.addEventListener("resize", handleScrollOrResize);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("scroll", handleScrollOrResize, true);
      window.removeEventListener("resize", handleScrollOrResize);
    };
  }, [isOpen]);

  if (!agencyId || !accessToken) return null;

  return (
    <div className="relative">
      <button
        ref={buttonRef}
        onClick={toggleOpen}
        className={`relative flex items-center gap-1 px-1.5 h-7 rounded-lg text-text-muted hover:text-text hover:bg-hover transition-all ${
          activeTimer ? "text-accent" : ""
        }`}
        title="Zaman Takibi"
        aria-haspopup="true"
        aria-expanded={isOpen}
        aria-controls={isOpen ? panelId : undefined}
      >
        <Clock className={`w-3.5 h-3.5 ${activeTimer ? "animate-pulse" : ""}`} />
        {activeTimer && (
          <span className="text-[10px] font-semibold tabular-nums">
            {formatBadgeElapsed(activeTimer.started_at, nowMs)}
          </span>
        )}
      </button>

      {isOpen &&
        mounted &&
        panelPos &&
        createPortal(
          <div
            ref={panelRef}
            id={panelId}
            role="dialog"
            aria-label="Zaman Takibi"
            style={{ position: "fixed", top: panelPos.top, left: panelPos.left, width: PANEL_WIDTH }}
            className="max-w-[90vw] bg-surface border border-border rounded-xl shadow-modal z-[9999] overflow-hidden p-4"
          >
            <TimerControls
              agencyId={agencyId}
              accessToken={accessToken}
              activeTimer={activeTimer}
              onStarted={(entry) => {
                setActiveTimer({
                  id: entry.id,
                  brief_id: entry.brief_id,
                  brand_id: entry.brand_id,
                  deliverable_id: entry.deliverable_id,
                  task_id: entry.task_id,
                  category: entry.category,
                  description: entry.description,
                  billable: entry.billable,
                  started_at: entry.started_at,
                });
                emitTimerChanged();
              }}
              onStopped={() => {
                setActiveTimer(null);
                setIsOpen(false);
                emitTimerChanged();
              }}
            />
            <button
              type="button"
              onClick={() => {
                setManualModalOpen(true);
                setIsOpen(false);
              }}
              className="w-full mt-3 pt-3 border-t border-border text-center text-[12px] font-medium text-accent hover:opacity-80 transition-opacity"
            >
              Manuel kayıt ekle
            </button>
          </div>,
          document.body
        )}

      <ManualEntryModal
        isOpen={manualModalOpen}
        onClose={() => setManualModalOpen(false)}
        agencyId={agencyId}
        accessToken={accessToken}
        onCreated={() => refreshActive()}
      />
    </div>
  );
}

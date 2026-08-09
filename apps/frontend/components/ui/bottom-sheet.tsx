"use client";

import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { type ReactNode, useEffect, useRef } from "react";
import { useBodyScrollLock } from "@/hooks/useBodyScrollLock";
import { useFocusTrap } from "@/hooks/useFocusTrap";
import { SafeAreaContainer } from "./safe-area-container";

interface BottomSheetProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
}

/**
 * Sheet sliding up from the bottom edge — the shared engine behind Modal's
 * small-viewport rendering. Rounded top corners, safe-area bottom padding,
 * independent internal scroll, sticky header/footer, focus trap + body
 * scroll lock (both via shared hooks so nested Modal-inside-Drawer opens
 * stay scroll-lock-safe).
 */
export function BottomSheet({ isOpen, onClose, title, description, children, footer }: BottomSheetProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  useBodyScrollLock(isOpen);
  useFocusTrap(panelRef, isOpen);

  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-end justify-center">
          <motion.div
            className="absolute inset-0 bg-black/60 backdrop-blur-md"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            onClick={onClose}
          />
          <motion.div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-label={title}
            tabIndex={-1}
            className="relative w-full max-h-[85vh] bg-surface border-t border-border rounded-t-3xl shadow-modal flex flex-col overflow-hidden outline-none"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="flex justify-center pt-2.5 pb-1 flex-shrink-0" aria-hidden="true">
              <div className="w-9 h-1 rounded-full bg-border-strong" />
            </div>

            <div className="flex items-start justify-between gap-3 px-5 pb-3 flex-shrink-0">
              <div className="min-w-0">
                <h2 className="text-sm font-semibold text-text tracking-tight truncate">{title}</h2>
                {description && (
                  <p className="text-xs text-text-muted mt-0.5 truncate">{description}</p>
                )}
              </div>
              <button
                onClick={onClose}
                className="w-11 h-11 -mr-2.5 -mt-1.5 flex items-center justify-center rounded-lg text-text-muted hover:text-text hover:bg-hover transition-colors flex-shrink-0"
                aria-label="Kapat"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-5 pb-5">{children}</div>

            {footer && (
              <SafeAreaContainer
                bottom
                minBottom="12px"
                className="flex-shrink-0 px-5 pt-3 border-t border-border flex items-center justify-end gap-2"
              >
                {footer}
              </SafeAreaContainer>
            )}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

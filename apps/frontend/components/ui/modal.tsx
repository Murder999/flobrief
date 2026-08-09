"use client";

import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { type ReactNode, useEffect, useRef } from "react";
import { useBreakpoint } from "@/hooks/useBreakpoint";
import { useBodyScrollLock } from "@/hooks/useBodyScrollLock";
import { useFocusTrap } from "@/hooks/useFocusTrap";
import { BottomSheet } from "./bottom-sheet";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  maxWidth?: "sm" | "md" | "lg";
}

const MAX_WIDTH = { sm: "max-w-sm", md: "max-w-md", lg: "max-w-lg" };

export function Modal({
  isOpen,
  onClose,
  title,
  children,
  maxWidth = "md",
}: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const { isMobile } = useBreakpoint();
  useBodyScrollLock(isOpen && !isMobile); // BottomSheet locks its own scroll on mobile
  useFocusTrap(panelRef, isOpen && !isMobile);

  useEffect(() => {
    if (!isOpen || isMobile) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [isOpen, isMobile, onClose]);

  // Below the `md` breakpoint, render through the shared BottomSheet engine
  // instead of a centered dialog — same content, same close/escape/focus
  // behavior, just mobile-appropriate chrome.
  if (isMobile) {
    return (
      <BottomSheet isOpen={isOpen} onClose={onClose} title={title}>
        {children}
      </BottomSheet>
    );
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
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
            className={`relative w-full ${MAX_WIDTH[maxWidth]} max-h-[85vh] bg-surface border border-border rounded-2xl shadow-modal overflow-hidden flex flex-col outline-none`}
            initial={{ opacity: 0, scale: 0.95, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: 4 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
          >
            {/* Header gradient strip */}
            <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/40 to-transparent" />

            <div className="flex items-center justify-between px-6 py-4 border-b border-border flex-shrink-0">
              <h2 className="text-sm font-semibold text-text tracking-tight">{title}</h2>
              <button
                onClick={onClose}
                className="w-7 h-7 flex items-center justify-center rounded-lg text-text-muted hover:text-text hover:bg-hover transition-colors"
                aria-label="Kapat"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="px-6 py-5 overflow-y-auto">{children}</div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

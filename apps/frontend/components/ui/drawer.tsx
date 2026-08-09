"use client";

import { cn } from "@/lib/utils";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { type ReactNode, useEffect, useRef } from "react";
import { useBodyScrollLock } from "@/hooks/useBodyScrollLock";
import { useFocusTrap } from "@/hooks/useFocusTrap";

interface DrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  width?: "sm" | "md" | "lg";
  footer?: ReactNode;
}

const WIDTH = { sm: "max-w-sm", md: "max-w-md", lg: "max-w-xl" };

/** Slide-in-from-right panel — same overlay/animation/escape-to-close
 * conventions as `Modal`, adapted to a side panel instead of a centered
 * dialog. Never exceeds viewport width (max-w-* capped, full width on
 * narrow screens). */
export function Drawer({
  isOpen,
  onClose,
  title,
  description,
  children,
  width = "md",
  footer,
}: DrawerProps) {
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
        <div className="fixed inset-0 z-50 flex justify-end">
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
            className={cn(
              "relative h-full w-full bg-surface border-l border-border shadow-modal flex flex-col overflow-hidden outline-none",
              WIDTH[width]
            )}
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="absolute inset-y-0 left-0 w-px bg-gradient-to-b from-transparent via-accent/40 to-transparent" />

            <div className="flex items-start justify-between gap-3 px-6 py-4 border-b border-border flex-shrink-0">
              <div className="min-w-0">
                <h2 className="text-sm font-semibold text-text tracking-tight truncate">{title}</h2>
                {description && (
                  <p className="text-xs text-text-muted mt-0.5 truncate">{description}</p>
                )}
              </div>
              <button
                onClick={onClose}
                className="w-7 h-7 flex items-center justify-center rounded-lg text-text-muted hover:text-text hover:bg-hover transition-colors flex-shrink-0"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-5">{children}</div>

            {footer && (
              <div className="flex-shrink-0 px-6 py-4 border-t border-border flex items-center justify-end gap-2">
                {footer}
              </div>
            )}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useLocale } from "@/context/locale-context";

interface InfoTooltipProps {
  targetRef?: React.RefObject<HTMLElement | null>;
  children?: React.ReactNode;
  text: string;
  title?: string;
  placement?: "top" | "bottom" | "left" | "right";
  learnMoreHref?: string;
}

const TOOLTIP_DELAY = 150;

export function InfoTooltip({ targetRef, children, text, title, placement = "top", learnMoreHref }: InfoTooltipProps) {
  const { t } = useLocale();
  const [show, setShow] = useState(false);
  const [anchor, setAnchor] = useState<DOMRect | null>(null);
  const wrapperRef = useRef<HTMLSpanElement>(null);
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cancelHide = useCallback(() => {
    if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    hideTimerRef.current = null;
  }, []);

  const scheduleHide = useCallback(() => {
    cancelHide();
    hideTimerRef.current = setTimeout(() => setShow(false), TOOLTIP_DELAY);
  }, [cancelHide]);

  useEffect(() => {
    const element = targetRef?.current ?? wrapperRef.current;
    if (!element) {
      setShow(false);
      return;
    }

    const updatePosition = () => {
      setAnchor(element.getBoundingClientRect());
    };

    const handleShow = () => {
      cancelHide();
      updatePosition();
      setShow(true);
    };
    const handleHide = scheduleHide;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setShow(false);
    };

    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    element.addEventListener("mouseenter", handleShow);
    element.addEventListener("mouseleave", handleHide);
    element.addEventListener("focusin", handleShow);
    element.addEventListener("focusout", handleHide);
    element.addEventListener("keydown", handleKeyDown);

    return () => {
      cancelHide();
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
      element.removeEventListener("mouseenter", handleShow);
      element.removeEventListener("mouseleave", handleHide);
      element.removeEventListener("focusin", handleShow);
      element.removeEventListener("focusout", handleHide);
      element.removeEventListener("keydown", handleKeyDown);
    };
  }, [cancelHide, scheduleHide, targetRef]);

  const position = anchor
    ? placement === "bottom"
      ? { top: anchor.bottom + 8, left: anchor.left + anchor.width / 2, transform: "translateX(-50%)" }
      : placement === "left"
        ? { top: anchor.top + anchor.height / 2, left: anchor.left - 8, transform: "translate(-100%, -50%)" }
        : placement === "right"
          ? { top: anchor.top + anchor.height / 2, left: anchor.right + 8, transform: "translateY(-50%)" }
          : { top: anchor.top - 8, left: anchor.left + anchor.width / 2, transform: "translate(-50%, -100%)" }
    : null;

  return (
    <>
      {children && <span ref={wrapperRef} className="block">{children}</span>}
      {show && position && createPortal(
        <div
          role="tooltip"
          aria-live="polite"
          className={`tooltip tooltip-${placement} fixed z-50 max-w-xs rounded-lg border border-border bg-surface p-3 text-sm text-text shadow-md`}
          style={position}
          onMouseEnter={cancelHide}
          onMouseLeave={scheduleHide}
          onFocus={cancelHide}
          onBlur={scheduleHide}
        >
          {title && <strong className="mb-1 block font-medium text-accent">{title}</strong>}
          <span className="text-text-muted">{text}</span>
          {learnMoreHref ? (
            <Link
              href={learnMoreHref}
              className="mt-2 block font-medium text-accent underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30"
            >
              {t("help.common.learnMore")}
            </Link>
          ) : null}
        </div>,
        document.body
      )}
    </>
  );
}

InfoTooltip.displayName = "InfoTooltip";

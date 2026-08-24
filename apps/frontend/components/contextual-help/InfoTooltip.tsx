"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

interface InfoTooltipProps {
  targetRef?: React.RefObject<HTMLElement | null>;
  children?: React.ReactNode;
  text: string;
  title?: string;
  placement?: "top" | "bottom" | "left" | "right";
}

const TOOLTIP_DELAY = 150;

export function InfoTooltip({ targetRef, children, text, title, placement = "top" }: InfoTooltipProps) {
  const [show, setShow] = useState(false);
  const [anchor, setAnchor] = useState<DOMRect | null>(null);
  const wrapperRef = useRef<HTMLSpanElement>(null);

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
      updatePosition();
      setShow(true);
    };
    const handleHide = () => setShow(false);
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
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
      element.removeEventListener("mouseenter", handleShow);
      element.removeEventListener("mouseleave", handleHide);
      element.removeEventListener("focusin", handleShow);
      element.removeEventListener("focusout", handleHide);
      element.removeEventListener("keydown", handleKeyDown);
    };
  }, [targetRef]);

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
        >
          {title && <strong className="mb-1 block font-medium text-accent">{title}</strong>}
          <span className="text-text-muted">{text}</span>
        </div>,
        document.body
      )}
    </>
  );
}

InfoTooltip.displayName = "InfoTooltip";

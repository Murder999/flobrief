"use client";

import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { type ButtonHTMLAttributes, forwardRef } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive" | "outline";
type ButtonSize = "sm" | "md" | "lg" | "icon" | "icon-sm";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-gradient-accent text-white shadow-sm hover:shadow-glow-sm hover:opacity-90 active:opacity-80",
  secondary:
    "border border-border bg-surface-2 text-text hover:border-border-hover hover:bg-surface-3 active:bg-surface-3",
  outline:
    "border border-border text-text-secondary hover:text-text hover:border-border-hover hover:bg-surface-2",
  ghost:
    "text-text-secondary hover:text-text hover:bg-hover active:bg-active",
  destructive:
    "bg-danger text-white hover:opacity-90 shadow-sm active:opacity-80",
};

const sizeClasses: Record<ButtonSize, string> = {
  "icon-sm": "h-7 w-7 p-0 text-xs",
  sm:        "h-8 px-3 text-xs gap-1.5 rounded-lg",
  md:        "h-9 px-4 text-sm gap-2 rounded-lg",
  lg:        "h-11 px-5 text-sm gap-2.5 rounded-xl",
  icon:      "h-9 w-9 p-0 rounded-lg",
};

const MotionButton = motion.button;

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    { className, variant = "primary", size = "md", isLoading = false, disabled, children, ...props },
    ref
  ) => {
    return (
      <MotionButton
        ref={ref}
        disabled={disabled || isLoading}
        whileTap={{ scale: disabled || isLoading ? 1 : 0.97 }}
        transition={{ duration: 0.1 }}
        className={cn(
          "inline-flex items-center justify-center font-medium transition-all duration-150",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30 focus-visible:ring-offset-1 focus-visible:ring-offset-background",
          "disabled:pointer-events-none disabled:opacity-50",
          variantClasses[variant],
          sizeClasses[size],
          className
        )}
        {...(props as React.ComponentProps<typeof MotionButton>)}
      >
        {isLoading ? (
          <svg className="h-4 w-4 animate-spin flex-shrink-0" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
            <path className="opacity-80" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        ) : null}
        {children}
      </MotionButton>
    );
  }
);

Button.displayName = "Button";

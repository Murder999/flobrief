"use client";

import { cn } from "@/lib/utils";
import { forwardRef, useId, type InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, hint, id, ...props }, ref) => {
    // A label-derived slug alone collides whenever two Input instances with
    // the same label render on the same page at once (e.g. the capacity
    // schedule page's TimeOffRequestForm and AllocationEditor both have a
    // "Başlangıç" field) -- two elements sharing one `id` is invalid HTML
    // and breaks the label->input association assistive tech relies on.
    // useId() guarantees per-instance uniqueness while keeping the label
    // slug for readability when inspecting the DOM.
    const generatedId = useId();
    const inputId = id || (label ? `${label.toLowerCase().replace(/\s+/g, "-")}-${generatedId}` : generatedId);

    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label
            htmlFor={inputId}
            className="text-xs font-medium text-text-muted tracking-wide"
          >
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={cn(
            "h-9 w-full rounded-lg bg-surface-2 border border-border px-3 text-sm text-text",
            "placeholder:text-text-placeholder",
            "transition-all duration-150",
            "focus:outline-none focus:border-accent/60 focus:ring-2 focus:ring-accent/15 focus:bg-surface",
            "disabled:opacity-50 disabled:pointer-events-none",
            error && "border-danger/50 focus:ring-danger/15 focus:border-danger/60",
            className
          )}
          {...props}
        />
        {error && (
          <p className="text-xs text-danger/80">{error}</p>
        )}
        {hint && !error && (
          <p className="text-xs text-text-muted">{hint}</p>
        )}
      </div>
    );
  }
);

Input.displayName = "Input";

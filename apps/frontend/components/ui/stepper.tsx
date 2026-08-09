"use client";

import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

export interface StepperStep {
  key: string;
  label: string;
}

interface StepperProps {
  steps: StepperStep[];
  activeIndex: number;
  onStepClick?: (index: number) => void;
  className?: string;
}

export function Stepper({ steps, activeIndex, onStepClick, className }: StepperProps) {
  return (
    <ol className={cn("flex items-center gap-1", className)}>
      {steps.map((step, index) => {
        const isDone = index < activeIndex;
        const isActive = index === activeIndex;
        const isClickable = Boolean(onStepClick) && index <= activeIndex;
        return (
          <li key={step.key} className="flex items-center flex-1 min-w-0 last:flex-none">
            <button
              type="button"
              disabled={!isClickable}
              onClick={() => onStepClick?.(index)}
              className={cn(
                "flex items-center gap-2 text-left",
                isClickable ? "cursor-pointer" : "cursor-default"
              )}
            >
              <span
                className={cn(
                  "flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-semibold transition-colors",
                  isDone && "bg-accent text-white",
                  isActive && !isDone && "bg-accent-subtle text-accent ring-2 ring-accent/40",
                  !isDone && !isActive && "bg-surface-2 text-text-muted"
                )}
              >
                {isDone ? <Check className="w-3.5 h-3.5" /> : index + 1}
              </span>
              <span
                className={cn(
                  "text-[12px] font-medium truncate hidden sm:inline",
                  isActive ? "text-text" : "text-text-muted"
                )}
              >
                {step.label}
              </span>
            </button>
            {index < steps.length - 1 && (
              <span
                className={cn(
                  "flex-1 h-px mx-2 min-w-[12px]",
                  isDone ? "bg-accent" : "bg-border"
                )}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}

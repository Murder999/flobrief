import { cn } from "@/lib/utils";
import { ChevronDown } from "lucide-react";
import type { SelectHTMLAttributes } from "react";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  options: { value: string; label: string; disabled?: boolean }[];
}

export function Select({ label, error, options, className = "", ...props }: SelectProps) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label className="text-xs font-medium text-text-muted tracking-wide">
          {label}
        </label>
      )}
      <div className="relative">
        <select
          className={cn(
            "w-full h-9 pl-3 pr-8 bg-surface-2 border border-border rounded-lg text-sm text-text appearance-none cursor-pointer",
            "transition-all duration-150",
            "focus:outline-none focus:border-accent/60 focus:ring-2 focus:ring-accent/15 focus:bg-surface",
            "disabled:opacity-50 disabled:pointer-events-none",
            error && "border-danger/50 focus:ring-danger/15 focus:border-danger/60",
            className
          )}
          {...props}
        >
          {options.map((opt) => (
            <option
              key={opt.value}
              value={opt.value}
              disabled={opt.disabled}
              className="bg-surface-2 text-text"
            >
              {opt.label}
            </option>
          ))}
        </select>
        <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted pointer-events-none" />
      </div>
      {error && <p className="text-xs text-danger/80">{error}</p>}
    </div>
  );
}

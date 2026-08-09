"use client";

import { useEffect, useState } from "react";
import { Sun, Moon, Monitor } from "lucide-react";
import { cn } from "@/lib/utils";
import { applyTheme, getTheme, type Theme } from "@/lib/theme";

const ICONS: Record<Theme, React.ReactNode> = {
  light: <Sun className="w-3.5 h-3.5" />,
  dark: <Moon className="w-3.5 h-3.5" />,
  system: <Monitor className="w-3.5 h-3.5" />,
};

const LABELS: Record<Theme, string> = {
  light: "Açık",
  dark: "Koyu",
  system: "Sistem",
};

interface ThemeToggleProps {
  /** Which side the dropdown opens toward relative to the trigger button. */
  menuPosition?: "up" | "down";
}

export function ThemeToggle({ menuPosition = "down" }: ThemeToggleProps) {
  const [theme, setTheme] = useState<Theme>("light");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setTheme(getTheme());
  }, []);

  const handleSelect = (mode: Theme) => {
    setTheme(mode);
    setOpen(false);
    applyTheme(mode);
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="p-1.5 rounded-lg text-text-muted hover:text-text hover:bg-hover transition-all"
        title="Tema"
      >
        {ICONS[theme]}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div
            className={cn(
              "absolute z-50 rounded-xl border border-border bg-surface shadow-dropdown overflow-hidden",
              menuPosition === "up"
                ? "bottom-full left-0 mb-1.5"
                : "top-full right-0 mt-1.5"
            )}
            style={{ minWidth: "140px" }}
          >
            {(["light", "dark", "system"] as Theme[]).map((mode) => (
              <button
                key={mode}
                onClick={() => handleSelect(mode)}
                className={cn(
                  "flex items-center gap-2.5 w-full px-3 py-2 text-xs transition-colors",
                  theme === mode
                    ? "text-accent bg-accent-subtle font-medium"
                    : "text-text-secondary hover:text-text hover:bg-hover"
                )}
              >
                {ICONS[mode]}
                {LABELS[mode]}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

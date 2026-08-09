import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        /* ── Surfaces ─────────────────────────────────────── */
        background:     "var(--color-background)",
        surface:        "var(--color-surface)",
        "surface-2":    "var(--color-surface-2)",
        "surface-3":    "var(--color-surface-3)",

        /* ── Borders ──────────────────────────────────────── */
        border:         "var(--color-border)",
        "border-hover": "var(--color-border-hover)",
        "border-strong":"var(--color-border-strong)",

        /* ── Text ─────────────────────────────────────────── */
        text:               "var(--color-text)",
        "text-secondary":   "var(--color-text-secondary)",
        "text-muted":       "var(--color-text-muted)",
        "text-placeholder": "var(--color-text-placeholder)",

        /* ── Brand accent ─────────────────────────────────── */
        accent:              "var(--color-accent)",
        "accent-hover":      "var(--color-accent-hover)",
        "accent-subtle":     "var(--color-accent-subtle)",
        "accent-text":       "var(--color-accent-text)",

        /* ── Semantic status ──────────────────────────────── */
        success: "var(--color-success)",
        warning: "var(--color-warning)",
        danger:  "var(--color-danger)",
        info:    "var(--color-info)",
        purple:  "var(--color-purple)",

        "success-subtle": "var(--color-success-subtle)",
        "warning-subtle": "var(--color-warning-subtle)",
        "danger-subtle":  "var(--color-danger-subtle)",
        "info-subtle":    "var(--color-info-subtle)",
        "purple-subtle":  "var(--color-purple-subtle)",

        "success-text": "var(--color-success-text)",
        "warning-text": "var(--color-warning-text)",
        "danger-text":  "var(--color-danger-text)",
        "info-text":    "var(--color-info-text)",
        "purple-text":  "var(--color-purple-text)",
      },

      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "Menlo", "Monaco", "monospace"],
      },

      fontSize: {
        "2xs": ["0.625rem", { lineHeight: "0.875rem" }],
        "3xs": ["0.5625rem", { lineHeight: "0.75rem" }],
      },

      letterSpacing: {
        tightest: "-0.04em",
        tighter:  "-0.025em",
        tight:    "-0.015em",
      },

      borderRadius: {
        DEFAULT: "8px",
        sm:   "6px",
        md:   "8px",
        lg:   "12px",
        xl:   "16px",
        "2xl": "20px",
        "3xl": "24px",
        "4xl": "32px",
      },

      boxShadow: {
        /* Static tokens that don't need theming */
        xs:    "var(--shadow-xs)",
        sm:    "var(--shadow-sm)",
        md:    "var(--shadow-md)",
        lg:    "var(--shadow-lg)",
        xl:    "var(--shadow-xl)",
        "2xl": "var(--shadow-2xl)",

        card:       "var(--shadow-card)",
        "card-hover": "var(--shadow-card-hover)",
        modal:      "var(--shadow-modal)",
        dropdown:   "var(--shadow-dropdown)",
        popover:    "var(--shadow-popover)",
        sidebar:    "var(--shadow-sidebar)",

        accent:   "var(--shadow-accent)",
        glow:     "var(--shadow-glow)",
        "glow-sm":"var(--shadow-glow-sm)",
      },

      backgroundImage: {
        "gradient-accent":        "var(--gradient-accent)",
        "gradient-accent-subtle": "var(--gradient-accent-subtle)",
        "gradient-surface":       "var(--gradient-surface)",
        "gradient-sidebar":       "var(--gradient-sidebar)",
        "gradient-hero":          "var(--gradient-hero)",
      },

      animation: {
        shimmer:     "shimmer 1.8s ease-in-out infinite",
        "fade-in":   "fade-in 200ms ease-out both",
        "scale-in":  "scale-in 200ms cubic-bezier(0.16, 1, 0.3, 1) both",
        "slide-up":  "slide-up 220ms cubic-bezier(0.16, 1, 0.3, 1) both",
        "fade-in-up":"fade-in-up 600ms cubic-bezier(0.16, 1, 0.3, 1) both",
      },

      keyframes: {
        shimmer: {
          "0%":   { backgroundPosition: "200% 0" },
          "100%": { backgroundPosition: "-200% 0" },
        },
        "fade-in": {
          "0%":   { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "scale-in": {
          "0%":   { opacity: "0", transform: "scale(0.96) translateY(4px)" },
          "100%": { opacity: "1", transform: "scale(1) translateY(0)" },
        },
        "slide-up": {
          "0%":   { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in-up": {
          "0%":   { opacity: "0", transform: "translateY(20px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },

      spacing: {
        "4.5": "1.125rem",
        "5.5": "1.375rem",
        "13": "3.25rem",
        "15": "3.75rem",
        "18": "4.5rem",
        "22": "5.5rem",
      },

      maxWidth: {
        container: "1280px",
        "container-sm": "960px",
        "container-xs": "720px",
      },

      transitionDuration: {
        instant:  "80ms",
        fast:     "150ms",
        standard: "240ms",
        slow:     "380ms",
      },

      transitionTimingFunction: {
        spring: "cubic-bezier(0.16, 1, 0.3, 1)",
        bounce: "cubic-bezier(0.34, 1.56, 0.64, 1)",
      },

      zIndex: {
        header:   "40",
        sidebar:  "30",
        dropdown: "50",
        modal:    "60",
        toast:    "70",
        tooltip:  "80",
      },
    },
  },
  plugins: [],
};

export default config;

export type Theme = "dark" | "light" | "system";

export function getTheme(): Theme {
  if (typeof window === "undefined") return "light";
  return (localStorage.getItem("flobrief-theme") as Theme) || "light";
}

export function applyTheme(theme: Theme) {
  const root = document.documentElement;
  if (theme === "system") {
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    root.setAttribute("data-theme", prefersDark ? "dark" : "light");
  } else {
    root.setAttribute("data-theme", theme);
  }
  localStorage.setItem("flobrief-theme", theme);
}

export function initTheme() {
  const saved = getTheme();
  applyTheme(saved);
}

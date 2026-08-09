"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

export type DateRangePreset = "last7" | "this_month" | "last_month" | "custom";

export interface DateRangeValue {
  preset: DateRangePreset | null;
  start: string | null;
  end: string | null;
}

// Local calendar date, not toISOString() — toISOString() converts to UTC
// first, which silently shifts the date across midnight for any user west
// of UTC. This must always match what the browser's own <input type="date">
// shows the user.
function localISODate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function presetRange(preset: Exclude<DateRangePreset, "custom">): { start: string; end: string } {
  const now = new Date();
  if (preset === "last7") {
    const end = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 6);
    return { start: localISODate(start), end: localISODate(end) };
  }
  if (preset === "this_month") {
    const start = new Date(now.getFullYear(), now.getMonth(), 1);
    const end = new Date(now.getFullYear(), now.getMonth() + 1, 0);
    return { start: localISODate(start), end: localISODate(end) };
  }
  // last_month
  const start = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  const end = new Date(now.getFullYear(), now.getMonth(), 0);
  return { start: localISODate(start), end: localISODate(end) };
}

const VALID_PRESETS: ReadonlySet<string> = new Set(["last7", "this_month", "last_month", "custom"]);
const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/** Shared URL-persisted date-range filter for the team-scoped time report
 * pages (/team, /by-brand, /missing). Deliberately not used by /my or
 * /weekly — those are self-service, single-week views with different
 * semantics; only /my silently accepts a start/end deep-link pair without
 * exposing this picker UI. */
export function useDateRangeFilter() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const rawPreset = searchParams.get("range");
  const rawStart = searchParams.get("start");
  const rawEnd = searchParams.get("end");

  const value: DateRangeValue = useMemo(() => {
    const preset = rawPreset && VALID_PRESETS.has(rawPreset) ? (rawPreset as DateRangePreset) : null;
    const start = rawStart && ISO_DATE_RE.test(rawStart) ? rawStart : null;
    const end = rawEnd && ISO_DATE_RE.test(rawEnd) ? rawEnd : null;
    return { preset, start, end };
  }, [rawPreset, rawStart, rawEnd]);

  const navigate = useCallback(
    (params: URLSearchParams) => {
      const query = params.toString();
      router.replace(query ? `${pathname}?${query}` : pathname);
    },
    [router, pathname]
  );

  const setPreset = useCallback(
    (preset: Exclude<DateRangePreset, "custom">) => {
      const { start, end } = presetRange(preset);
      const params = new URLSearchParams(searchParams.toString());
      params.set("range", preset);
      params.set("start", start);
      params.set("end", end);
      navigate(params);
    },
    [searchParams, navigate]
  );

  const setCustomDates = useCallback(
    (start: string, end: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("range", "custom");
      params.set("start", start);
      params.set("end", end);
      navigate(params);
    },
    [searchParams, navigate]
  );

  const clear = useCallback(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("range");
    params.delete("start");
    params.delete("end");
    navigate(params);
  }, [searchParams, navigate]);

  const apiParams = useMemo(
    () =>
      value.start && value.end
        ? { start_date: value.start, end_date: value.end }
        : undefined,
    [value.start, value.end]
  );

  return { ...value, apiParams, setPreset, setCustomDates, clear };
}

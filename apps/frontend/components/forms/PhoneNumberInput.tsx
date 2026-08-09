"use client";

import { cn } from "@/lib/utils";
import { useEffect, useRef, useState } from "react";

interface Country {
  code: string;
  name: string;
  dialCode: string;
  flag: string;
}

export const PHONE_COUNTRIES: Country[] = [
  { code: "TR", name: "Türkiye", dialCode: "+90", flag: "🇹🇷" },
  { code: "US", name: "ABD", dialCode: "+1", flag: "🇺🇸" },
  { code: "GB", name: "İngiltere", dialCode: "+44", flag: "🇬🇧" },
  { code: "DE", name: "Almanya", dialCode: "+49", flag: "🇩🇪" },
  { code: "FR", name: "Fransa", dialCode: "+33", flag: "🇫🇷" },
  { code: "NL", name: "Hollanda", dialCode: "+31", flag: "🇳🇱" },
  { code: "AE", name: "BAE", dialCode: "+971", flag: "🇦🇪" },
  { code: "SA", name: "Suudi Arabistan", dialCode: "+966", flag: "🇸🇦" },
  { code: "AZ", name: "Azerbaycan", dialCode: "+994", flag: "🇦🇿" },
  { code: "CY", name: "Kıbrıs", dialCode: "+357", flag: "🇨🇾" },
];

function formatSubscriberDisplay(digits: string): string {
  if (digits.length <= 3) return digits;
  if (digits.length <= 6) return `${digits.slice(0, 3)} ${digits.slice(3)}`;
  if (digits.length <= 10) return `${digits.slice(0, 3)} ${digits.slice(3, 6)} ${digits.slice(6)}`;
  return `${digits.slice(0, 3)} ${digits.slice(3, 6)} ${digits.slice(6, 9)} ${digits.slice(9)}`;
}

function parseE164(e164: string, defaultCode: string): { country: Country; subscriberDigits: string } {
  const defaultCountry = PHONE_COUNTRIES.find((c) => c.code === defaultCode) ?? PHONE_COUNTRIES[0];
  if (!e164 || !e164.startsWith("+")) {
    const digits = e164.replace(/\D/g, "").replace(/^0/, "");
    return { country: defaultCountry, subscriberDigits: digits };
  }
  const sorted = [...PHONE_COUNTRIES].sort((a, b) => b.dialCode.length - a.dialCode.length);
  for (const c of sorted) {
    if (e164.startsWith(c.dialCode)) {
      return { country: c, subscriberDigits: e164.slice(c.dialCode.length).replace(/\D/g, "") };
    }
  }
  return { country: defaultCountry, subscriberDigits: e164.replace(/\D/g, "") };
}

export interface PhoneNumberInputProps {
  value?: string;
  onChange?: (e164: string) => void;
  defaultCountry?: string;
  error?: string;
  disabled?: boolean;
  required?: boolean;
  label?: string;
  helperText?: string;
  id?: string;
}

export function PhoneNumberInput({
  value = "",
  onChange,
  defaultCountry = "TR",
  error,
  disabled,
  required,
  label,
  helperText,
  id = "phone-input",
}: PhoneNumberInputProps) {
  const initialParsed = parseE164(value, defaultCountry);
  const [selectedCountry, setSelectedCountry] = useState<Country>(initialParsed.country);
  const [subscriberDigits, setSubscriberDigits] = useState(initialParsed.subscriberDigits);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [search, setSearch] = useState("");

  const prevValueRef = useRef(value);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const [menuLeft, setMenuLeft] = useState(0);

  // The menu is `absolute left-0` by default (aligned to the country
  // button); on a narrow viewport, if this field sits near the right edge
  // of its container the fixed 256px-wide menu can run off-screen. Nudge it
  // left just enough to stay on-screen, mirroring the clamp NotificationBell
  // already does for its own popover.
  useEffect(() => {
    if (!dropdownOpen) return;
    const wrapper = dropdownRef.current;
    if (!wrapper) return;
    const MENU_WIDTH = 256;
    const MARGIN = 8;
    const rect = wrapper.getBoundingClientRect();
    const overflowRight = rect.left + MENU_WIDTH - (window.innerWidth - MARGIN);
    setMenuLeft(overflowRight > 0 ? -overflowRight : 0);
  }, [dropdownOpen]);

  // Sync external value changes (e.g. form reset, profile load)
  useEffect(() => {
    if (value !== prevValueRef.current) {
      prevValueRef.current = value;
      const parsed = parseE164(value, defaultCountry);
      setSelectedCountry(parsed.country);
      setSubscriberDigits(parsed.subscriberDigits);
    }
  }, [value, defaultCountry]);

  useEffect(() => {
    function handleOutsideClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
        setSearch("");
      }
    }
    if (dropdownOpen) {
      document.addEventListener("mousedown", handleOutsideClick);
      return () => document.removeEventListener("mousedown", handleOutsideClick);
    }
  }, [dropdownOpen]);

  useEffect(() => {
    if (dropdownOpen) {
      const t = setTimeout(() => searchRef.current?.focus(), 40);
      return () => clearTimeout(t);
    }
  }, [dropdownOpen]);

  const filtered = PHONE_COUNTRIES.filter(
    (c) =>
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.dialCode.includes(search) ||
      c.code.toLowerCase().includes(search.toLowerCase())
  );

  const emitChange = (dialCode: string, digits: string) => {
    const e164 = digits ? `${dialCode}${digits}` : "";
    prevValueRef.current = e164;
    onChange?.(e164);
  };

  const handleCountrySelect = (country: Country) => {
    setSelectedCountry(country);
    setDropdownOpen(false);
    setSearch("");
    emitChange(country.dialCode, subscriberDigits);
  };

  const handleInputChange = (raw: string) => {
    const digits = raw.replace(/\D/g, "").replace(/^0/, "");
    setSubscriberDigits(digits);
    emitChange(selectedCountry.dialCode, digits);
  };

  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label htmlFor={id} className="text-xs font-medium text-text-muted tracking-wide">
          {label}
          {required && <span className="text-danger ml-1">*</span>}
        </label>
      )}

      <div
        className={cn(
          "flex items-stretch rounded-lg border bg-surface-2 overflow-visible transition-all duration-150",
          "focus-within:ring-2 focus-within:bg-surface",
          error
            ? "border-danger/50 focus-within:ring-danger/15 focus-within:border-danger/60"
            : "border-border focus-within:border-accent/60 focus-within:ring-accent/15",
          disabled && "opacity-50 pointer-events-none"
        )}
      >
        {/* Country selector */}
        <div className="relative flex-shrink-0" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => !disabled && setDropdownOpen((o) => !o)}
            disabled={disabled}
            className={cn(
              "flex items-center gap-1.5 px-3 h-9 rounded-l-lg",
              "border-r border-border hover:bg-surface transition-colors",
              "focus:outline-none select-none text-sm"
            )}
          >
            <span className="text-base leading-none">{selectedCountry.flag}</span>
            <span className="text-text-muted text-xs font-medium tabular-nums">
              {selectedCountry.dialCode}
            </span>
            <svg
              className={cn(
                "w-3 h-3 text-text-muted transition-transform duration-150",
                dropdownOpen && "rotate-180"
              )}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {dropdownOpen && (
            <div
              className="absolute top-full mt-1.5 z-50 w-64 max-w-[calc(100vw-1rem)] bg-surface border border-border rounded-xl shadow-modal overflow-hidden"
              style={{ left: menuLeft }}
            >
              <div className="p-2 border-b border-border">
                <div className="relative">
                  <svg
                    className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted pointer-events-none"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                    />
                  </svg>
                  <input
                    ref={searchRef}
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Ülke ara…"
                    className={cn(
                      "w-full pl-7 pr-3 py-1.5 text-xs rounded-lg",
                      "bg-surface-2 border border-border text-text placeholder-text-muted/50",
                      "focus:outline-none focus:border-accent/60 focus:ring-1 focus:ring-accent/15"
                    )}
                  />
                </div>
              </div>
              <div className="max-h-48 overflow-y-auto py-1">
                {filtered.length === 0 ? (
                  <div className="px-3 py-4 text-xs text-text-muted text-center">Ülke bulunamadı</div>
                ) : (
                  filtered.map((c) => (
                    <button
                      key={c.code}
                      type="button"
                      onClick={() => handleCountrySelect(c)}
                      className={cn(
                        "w-full flex items-center gap-2.5 px-3 py-2 text-left transition-colors",
                        selectedCountry.code === c.code
                          ? "bg-accent/10 text-accent"
                          : "hover:bg-surface-2 text-text"
                      )}
                    >
                      <span className="text-base">{c.flag}</span>
                      <span className="flex-1 text-xs font-medium">{c.name}</span>
                      <span className="text-xs text-text-muted tabular-nums">{c.dialCode}</span>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* Subscriber number input */}
        <input
          id={id}
          type="tel"
          value={formatSubscriberDisplay(subscriberDigits)}
          onChange={(e) => handleInputChange(e.target.value)}
          placeholder="531 554 08 64"
          disabled={disabled}
          className={cn(
            "flex-1 h-9 px-3 text-sm text-text bg-transparent rounded-r-lg",
            "placeholder:text-text-muted/50",
            "focus:outline-none"
          )}
          autoComplete="tel-national"
          inputMode="tel"
        />
      </div>

      {error && <p className="text-xs text-danger/80">{error}</p>}
      {helperText && !error && <p className="text-xs text-text-muted">{helperText}</p>}
    </div>
  );
}

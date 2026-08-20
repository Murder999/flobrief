import type { Locale } from "./config";
import { messages, type TranslationKey } from "@/messages";

export type TranslationValues = Record<string, string | number>;

export function translate(locale: Locale, key: TranslationKey, values?: TranslationValues): string {
  const template = messages[locale][key] ?? messages.en[key];
  if (!values) return template;

  return template.replace(/\{([A-Za-z0-9_]+)\}/g, (match, name: string) => {
    const value = values[name];
    return value === undefined ? match : String(value);
  });
}

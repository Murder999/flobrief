import type { Locale } from "@/lib/i18n/config";
import { enMessages, type TranslationKey } from "./en";
import { trMessages } from "./tr";

export { type TranslationKey } from "./en";

export const messages: Record<Locale, Record<TranslationKey, string>> = {
  en: enMessages,
  tr: trMessages,
};

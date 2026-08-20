import { auth } from "./auth";
import { briefs } from "./briefs";
import { common } from "./common";
import { dashboard } from "./dashboard";
import { marketing } from "./marketing";
import { notifications } from "./notifications";
import { portal } from "./portal";
import { settings } from "./settings";

export const enMessages = {
  ...common,
  ...auth,
  ...marketing,
  ...dashboard,
  ...briefs,
  ...portal,
  ...notifications,
  ...settings,
} as const;

export type TranslationKey = keyof typeof enMessages;

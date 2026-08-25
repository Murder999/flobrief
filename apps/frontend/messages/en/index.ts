import { auth } from "./auth";
import { briefs } from "./briefs";
import { common } from "./common";
import { dashboard } from "./dashboard";
import { help } from "./help";
import { marketing } from "./marketing";
import { notifications } from "./notifications";
import { portal } from "./portal";
import { platform } from "./platform";
import { reports } from "./reports";
import { settings } from "./settings";

export const enMessages = {
  ...common,
  ...auth,
  ...marketing,
  ...dashboard,
  ...help,
  ...briefs,
  ...portal,
  ...platform,
  ...reports,
  ...notifications,
  ...settings,
} as const;

export type TranslationKey = keyof typeof enMessages;

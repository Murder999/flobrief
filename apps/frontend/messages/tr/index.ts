import type { TranslationKey } from "../en";
import { auth } from "./auth";
import { briefs } from "./briefs";
import { common } from "./common";
import { dashboard } from "./dashboard";
import { marketing } from "./marketing";
import { notifications } from "./notifications";
import { portal } from "./portal";
import { reports } from "./reports";
import { settings } from "./settings";

export const trMessages = {
  ...common,
  ...auth,
  ...marketing,
  ...dashboard,
  ...briefs,
  ...portal,
  ...reports,
  ...notifications,
  ...settings,
} satisfies Record<TranslationKey, string>;

import type { TranslationKey } from "../en";
import { auth } from "./auth";
import { briefs } from "./briefs";
import { common } from "./common";
import { dashboard } from "./dashboard";
import { marketing } from "./marketing";
import { notifications } from "./notifications";
import { portal } from "./portal";
import { settings } from "./settings";

export const trMessages = {
  ...common,
  ...auth,
  ...marketing,
  ...dashboard,
  ...briefs,
  ...portal,
  ...notifications,
  ...settings,
} satisfies Record<TranslationKey, string>;

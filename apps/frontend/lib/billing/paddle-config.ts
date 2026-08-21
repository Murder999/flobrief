export type PlanCode =
  | "brand_solo"
  | "starter_agency"
  | "pro_agency"
  | "agency_plus"
  | "enterprise";

export type BillingPeriod = "monthly" | "yearly";

export interface PaddlePriceIds {
  monthly?: string;
  yearly?: string;
}

export interface PlanPaddleConfig {
  [planCode: string]: PaddlePriceIds;
}

function getEnv(key: string): string | undefined {
  const value = process.env[key];
  if (!value || value.trim() === "") return undefined;
  return value;
}

function requireEnv(key: string): string {
  const value = getEnv(key);
  if (!value) {
    throw new Error(`Missing required environment variable: ${key}`);
  }
  return value;
}

export function getPaddleClientToken(): string {
  return requireEnv("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN");
}

export const PADDLE_PRICE_IDS: PlanPaddleConfig = {
  brand_solo: {
    monthly: getEnv("NEXT_PUBLIC_PADDLE_PRICE_BRAND_SOLO_MONTHLY"),
    yearly: getEnv("NEXT_PUBLIC_PADDLE_PRICE_BRAND_SOLO_YEARLY"),
  },
  starter_agency: {
    monthly: getEnv("NEXT_PUBLIC_PADDLE_PRICE_STARTER_AGENCY_MONTHLY"),
    yearly: getEnv("NEXT_PUBLIC_PADDLE_PRICE_STARTER_AGENCY_YEARLY"),
  },
  pro_agency: {
    monthly: getEnv("NEXT_PUBLIC_PADDLE_PRICE_PRO_AGENCY_MONTHLY"),
    yearly: getEnv("NEXT_PUBLIC_PADDLE_PRICE_PRO_AGENCY_YEARLY"),
  },
  agency_plus: {
    monthly: getEnv("NEXT_PUBLIC_PADDLE_PRICE_AGENCY_PLUS_MONTHLY"),
    yearly: getEnv("NEXT_PUBLIC_PADDLE_PRICE_AGENCY_PLUS_YEARLY"),
  },
  enterprise: {
    monthly: undefined,
    yearly: undefined,
  },
};

export function getPriceId(planCode: PlanCode, period: BillingPeriod): string | undefined {
  const config = PADDLE_PRICE_IDS[planCode];
  if (!config) return undefined;
  return period === "monthly" ? config.monthly : config.yearly;
}

export function hasPriceId(planCode: PlanCode, period: BillingPeriod): boolean {
  return Boolean(getPriceId(planCode, period));
}

export function getAllPriceIds(): string[] {
  const ids: string[] = [];
  for (const config of Object.values(PADDLE_PRICE_IDS)) {
    if (config.monthly) ids.push(config.monthly);
    if (config.yearly) ids.push(config.yearly);
  }
  return ids;
}

export function mapPaddleLocale(locale: "tr" | "en"): string {
  return locale === "tr" ? "tr" : "en";
}
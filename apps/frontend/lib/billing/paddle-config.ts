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

const PUBLIC_PADDLE_ENV = {
  NEXT_PUBLIC_PADDLE_CLIENT_TOKEN: process.env.NEXT_PUBLIC_PADDLE_CLIENT_TOKEN,
  NEXT_PUBLIC_PADDLE_PRICE_BRAND_SOLO_MONTHLY:
    process.env.NEXT_PUBLIC_PADDLE_PRICE_BRAND_SOLO_MONTHLY,
  NEXT_PUBLIC_PADDLE_PRICE_BRAND_SOLO_YEARLY:
    process.env.NEXT_PUBLIC_PADDLE_PRICE_BRAND_SOLO_YEARLY,
  NEXT_PUBLIC_PADDLE_PRICE_STARTER_AGENCY_MONTHLY:
    process.env.NEXT_PUBLIC_PADDLE_PRICE_STARTER_AGENCY_MONTHLY,
  NEXT_PUBLIC_PADDLE_PRICE_STARTER_AGENCY_YEARLY:
    process.env.NEXT_PUBLIC_PADDLE_PRICE_STARTER_AGENCY_YEARLY,
  NEXT_PUBLIC_PADDLE_PRICE_PRO_AGENCY_MONTHLY:
    process.env.NEXT_PUBLIC_PADDLE_PRICE_PRO_AGENCY_MONTHLY,
  NEXT_PUBLIC_PADDLE_PRICE_PRO_AGENCY_YEARLY:
    process.env.NEXT_PUBLIC_PADDLE_PRICE_PRO_AGENCY_YEARLY,
  NEXT_PUBLIC_PADDLE_PRICE_AGENCY_PLUS_MONTHLY:
    process.env.NEXT_PUBLIC_PADDLE_PRICE_AGENCY_PLUS_MONTHLY,
  NEXT_PUBLIC_PADDLE_PRICE_AGENCY_PLUS_YEARLY:
    process.env.NEXT_PUBLIC_PADDLE_PRICE_AGENCY_PLUS_YEARLY,
} as const;

type PublicPaddleEnvKey = keyof typeof PUBLIC_PADDLE_ENV;

export class PaddleConfigurationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PaddleConfigurationError";
  }
}

function getEnv(key: PublicPaddleEnvKey): string | undefined {
  const value = PUBLIC_PADDLE_ENV[key];
  if (!value || value.trim() === "") return undefined;
  return value.trim();
}

function requireEnv(key: PublicPaddleEnvKey): string {
  const value = getEnv(key);
  if (!value) {
    console.error(`[Paddle:configuration] Missing required public variable: ${key}`);
    throw new PaddleConfigurationError(`Missing required public Paddle variable: ${key}`);
  }
  return value;
}

export function getPaddleClientToken(): string {
  return requireEnv("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN");
}

export function getPaddleEnvironment(token: string): "production" | "sandbox" {
  if (token.startsWith("live_")) return "production";
  if (token.startsWith("test_")) return "sandbox";

  console.error("[Paddle:configuration] Client token has an unsupported environment prefix");
  throw new PaddleConfigurationError("Invalid Paddle client token environment prefix");
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

export function requirePriceId(planCode: PlanCode, period: BillingPeriod): string {
  const priceId = getPriceId(planCode, period);
  if (!priceId) {
    console.error(
      `[Paddle:configuration] Missing price ID for plan=${planCode} period=${period}`
    );
    throw new PaddleConfigurationError(
      `Missing Paddle price ID for plan=${planCode} period=${period}`
    );
  }
  return priceId;
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

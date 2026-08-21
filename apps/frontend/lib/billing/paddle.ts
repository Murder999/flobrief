"use client";

import { initializePaddle, Paddle, PricePreviewParams, PricePreviewResponse } from "@paddle/paddle-js";
import { getPaddleClientToken } from "./paddle-config";
import { getPriceId } from "./paddle-config";

let paddleInstance: Paddle | null = null;
let initializationPromise: Promise<Paddle> | null = null;

export async function getPaddle(): Promise<Paddle> {
  if (paddleInstance) return paddleInstance;

  if (!initializationPromise) {
    initializationPromise = (async () => {
      const token = getPaddleClientToken();
      const paddle = await initializePaddle({
        token,
        environment: "production",
      });
      if (!paddle) {
        throw new Error("Paddle initialization failed");
      }
      paddleInstance = paddle;
      return paddle;
    })();
  }

  return initializationPromise;
}

export function resetPaddle(): void {
  paddleInstance = null;
  initializationPromise = null;
}

export async function openCheckout(params: {
  planCode: "brand_solo" | "starter_agency" | "pro_agency" | "agency_plus";
  period: "monthly" | "yearly";
  locale?: "tr" | "en";
  customerEmail?: string;
  yearly: boolean;
  planId: string;
}): Promise<void> {
  const priceId = getPriceId(params.planCode, params.period);
  if (!priceId) {
    throw new Error(`No Paddle price ID configured for ${params.planCode} ${params.period}`);
  }

  const paddle = await getPaddle();

  const items = [{ priceId, quantity: 1 }];

  await paddle.Checkout.open({
    items,
    settings: {
      displayMode: "overlay",
      variant: "one-page",
      locale: params.locale,
    },
    customer: params.customerEmail ? { email: params.customerEmail } : undefined,
  });
}

export async function previewPrices(
  priceIds: string[],
  locale: "tr" | "en" = "en"
): Promise<Map<string, { formattedTotal: string; currencyCode: string }>> {
  const paddle = await getPaddle();
  const results = new Map<string, { formattedTotal: string; currencyCode: string }>();

  try {
    const previewParams: PricePreviewParams = {
      items: priceIds.map((priceId) => ({ priceId, quantity: 1 })),
    };

    const preview = await paddle.PricePreview(previewParams) as PricePreviewResponse & { items?: Array<{ priceId: string; totals?: { total?: { formatted: string; currencyCode: string } } }> };

    if (preview.items) {
      for (const item of preview.items) {
        const priceId = item.priceId;
        const total = item.totals?.total?.formatted;
        const currency = item.totals?.total?.currencyCode;

        if (priceId && total && currency) {
          results.set(priceId, {
            formattedTotal: total,
            currencyCode: currency,
          });
        }
      }
    }
  } catch (error) {
    console.error("Paddle PricePreview failed:", error);
  }

  return results;
}
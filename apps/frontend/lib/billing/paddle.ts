"use client";

import { initializePaddle, Paddle, PricePreviewParams } from "@paddle/paddle-js";
import {
  getPaddleClientToken,
  getPaddleEnvironment,
  requirePriceId,
} from "./paddle-config";

let paddleInstance: Paddle | null = null;
let initializationPromise: Promise<Paddle> | null = null;

class PaddleInitializationError extends Error {
  constructor() {
    super("Paddle could not be initialized");
    this.name = "PaddleInitializationError";
  }
}

class PaddlePricePreviewError extends Error {
  constructor() {
    super("Paddle price preview could not be loaded");
    this.name = "PaddlePricePreviewError";
  }
}

class PaddleCheckoutError extends Error {
  constructor() {
    super("Paddle checkout could not be opened");
    this.name = "PaddleCheckoutError";
  }
}

function safeErrorMessage(error: unknown): string {
  let message: string;
  if (error instanceof Error) message = error.message;
  else if (typeof error === "string") message = error;
  else {
    try {
      message = JSON.stringify(error) || "Unknown Paddle error";
    } catch {
      message = "Unknown Paddle error";
    }
  }
  return message
    .replace(/\b(?:live|test)_[A-Za-z0-9_-]+\b/g, "[client-token-redacted]")
    .replace(/\bpri_[A-Za-z0-9_-]+\b/g, "[price-id-redacted]");
}

export async function getPaddle(): Promise<Paddle> {
  if (paddleInstance) return paddleInstance;

  if (!initializationPromise) {
    initializationPromise = (async () => {
      const token = getPaddleClientToken();
      const environment = getPaddleEnvironment(token);

      try {
        const paddle = await initializePaddle({ token, environment });
        if (!paddle || !paddle.Initialized) {
          throw new Error("SDK did not initialize a Paddle instance");
        }
        paddleInstance = paddle;
        return paddle;
      } catch (error) {
        initializationPromise = null;
        console.error(`[Paddle:initialization] ${safeErrorMessage(error)}`);
        throw new PaddleInitializationError();
      }
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
  const priceId = requirePriceId(params.planCode, params.period);

  const paddle = await getPaddle();

  const items = [{ priceId, quantity: 1 }];

  try {
    await paddle.Checkout.open({
      items,
      settings: {
        displayMode: "overlay",
        variant: "one-page",
        locale: params.locale,
      },
      customer: params.customerEmail ? { email: params.customerEmail } : undefined,
    });
  } catch (error) {
    console.error(`[Paddle:checkout] ${safeErrorMessage(error)}`);
    throw new PaddleCheckoutError();
  }
}

export async function previewPrices(
  priceIds: string[]
): Promise<Map<string, { formattedTotal: string; currencyCode: string }>> {
  const paddle = await getPaddle();
  const results = new Map<string, { formattedTotal: string; currencyCode: string }>();
  const requestedPriceIds = new Set(priceIds);

  try {
    const previewParams: PricePreviewParams = {
      items: priceIds.map((priceId) => ({ priceId, quantity: 1 })),
    };

    const preview = await paddle.PricePreview(previewParams);
    const currencyCode = preview.data.currencyCode;

    for (const lineItem of preview.data.details.lineItems) {
      const priceId = lineItem.price.id;
      if (requestedPriceIds.has(priceId) && lineItem.formattedTotals.total) {
        results.set(priceId, {
          formattedTotal: lineItem.formattedTotals.total,
          currencyCode,
        });
      }
    }

    if (results.size !== requestedPriceIds.size) {
      throw new Error("PricePreview response omitted one or more requested prices");
    }
  } catch (error) {
    console.error(`[Paddle:price-preview] ${safeErrorMessage(error)}`);
    throw new PaddlePricePreviewError();
  }

  return results;
}

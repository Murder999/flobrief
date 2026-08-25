"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { requirePriceId, type PlanCode } from "./paddle-config";
import { previewPrices } from "./paddle";

export interface PricePreviewResult {
  formattedTotal: string;
  currencyCode: string;
}

export function usePaddlePricePreview(
  planCode: PlanCode | null,
  period: "monthly" | "yearly"
): {
  price: PricePreviewResult | null;
  loading: boolean;
  error: Error | null;
  retry: () => Promise<void>;
} {
  const [price, setPrice] = useState<PricePreviewResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const requestIdRef = useRef(0);

  const fetchPrice = useCallback(async () => {
    const requestId = ++requestIdRef.current;

    if (!planCode) {
      setPrice(null);
      setError(null);
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setPrice(null);
      const priceId = requirePriceId(planCode, period);
      const results = await previewPrices([priceId]);
      const result = results.get(priceId);
      if (!result) throw new Error("Requested Paddle price was not returned");
      if (requestId === requestIdRef.current) setPrice(result);
    } catch (err) {
      if (requestId === requestIdRef.current) {
        setError(err instanceof Error ? err : new Error("Failed to fetch price"));
        setPrice(null);
      }
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  }, [planCode, period]);

  useEffect(() => {
    fetchPrice();
  }, [fetchPrice]);

  return { price, loading, error, retry: fetchPrice };
}

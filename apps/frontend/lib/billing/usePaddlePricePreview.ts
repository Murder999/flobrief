"use client";

import { useEffect, useState, useCallback } from "react";
import { useLocale } from "@/context/locale-context";
import { getAllPriceIds, getPriceId, type PlanCode } from "./paddle-config";
import { previewPrices } from "./paddle";

export interface PricePreviewResult {
  formattedTotal: string;
  currencyCode: string;
}

export function usePaddlePricePreview(
  planCode: PlanCode | null,
  period: "monthly" | "yearly"
): { price: PricePreviewResult | null; loading: boolean; error: Error | null } {
  const { locale } = useLocale();
  const [price, setPrice] = useState<PricePreviewResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchPrice = useCallback(async () => {
    if (!planCode) {
      setPrice(null);
      setLoading(false);
      return;
    }

    const priceId = getPriceId(planCode, period);

    if (!priceId) {
      setPrice(null);
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      const results = await previewPrices([priceId], locale);
      const result = results.get(priceId);
      if (result) {
        setPrice(result);
      } else {
        setPrice(null);
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error("Failed to fetch price"));
      setPrice(null);
    } finally {
      setLoading(false);
    }
  }, [planCode, period, locale]);

  useEffect(() => {
    fetchPrice();
  }, [fetchPrice]);

  return { price, loading, error };
}

export function useAllPaddlePrices(): Map<string, { formattedTotal: string; currencyCode: string }> {
  const { locale } = useLocale();
  const [prices, setPrices] = useState<Map<string, { formattedTotal: string; currencyCode: string }>>(new Map());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    const fetchAll = async () => {
      try {
        setLoading(true);
        const priceIds = getAllPriceIds();
        if (priceIds.length === 0) {
          setPrices(new Map());
          return;
        }
        const results = await previewPrices(priceIds, locale);
        if (mounted) {
          setPrices(results);
        }
      } catch (err) {
        console.error("Failed to fetch all prices:", err);
        if (mounted) setPrices(new Map());
      } finally {
        if (mounted) setLoading(false);
      }
    };

    fetchAll();

    return () => {
      mounted = false;
    };
  }, [locale]);

  return prices;
}
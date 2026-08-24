"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { request } from "@/services/api";

export interface ScraperConfig {
  request_delay_seconds: number;
  enrichment_concurrency: number;
  socket_timeout: number;
  retries: number;
  retry_backoff: number;
}

export interface ScraperPreset {
  label: string;
  description: string;
  request_delay_seconds: number;
  enrichment_concurrency: number;
  socket_timeout: number;
}

export const PRESETS: Record<string, ScraperPreset> = {
  fast: {
    label: "Fast",
    description: "High concurrency, minimal delay. Best for small crawls.",
    request_delay_seconds: 0.05,
    enrichment_concurrency: 10,
    socket_timeout: 20,
  },
  balanced: {
    label: "Balanced",
    description: "Moderate speed with reasonable safety.",
    request_delay_seconds: 0.2,
    enrichment_concurrency: 6,
    socket_timeout: 25,
  },
  default: {
    label: "Default",
    description: "Safe defaults for most use cases.",
    request_delay_seconds: 0.5,
    enrichment_concurrency: 4,
    socket_timeout: 30,
  },
  slow: {
    label: "Slow",
    description: "Conservative pacing. Avoids rate limits.",
    request_delay_seconds: 1.0,
    enrichment_concurrency: 2,
    socket_timeout: 45,
  },
};

const scraperKeys = {
  config: ["scraper", "config"] as const,
};

export function useScraperConfig() {
  return useQuery({
    queryKey: scraperKeys.config,
    queryFn: () => request<ScraperConfig>("/scraper/config"),
  });
}

export function useUpdateScraperConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<ScraperConfig>) =>
      request<ScraperConfig>("/scraper/config", {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: scraperKeys.config });
    },
  });
}

export function useApplyPreset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (preset: string) =>
      request<ScraperConfig & { applied_preset: string }>(
        "/scraper/config/preset",
        { method: "POST", body: JSON.stringify({ preset }) },
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: scraperKeys.config });
    },
  });
}

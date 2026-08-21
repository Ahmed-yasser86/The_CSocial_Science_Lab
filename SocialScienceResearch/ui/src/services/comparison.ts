"use client";

import { useMutation } from "@tanstack/react-query";
import { request } from "@/services/api";
import type {
  CohortComparison,
  CompareChannelsInput,
  CompareCohortsInput,
  ComparePeriodsInput,
  CompareRunsInput,
  CompareVideosInput,
  EntityComparison,
  PeriodComparison,
  RunComparison,
} from "@/lib/comparison-types";

export function compareVideos(body: CompareVideosInput): Promise<EntityComparison> {
  return request("/comparison/videos", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function compareChannels(body: CompareChannelsInput): Promise<EntityComparison> {
  return request("/comparison/channels", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function comparePeriods(body: ComparePeriodsInput): Promise<PeriodComparison> {
  return request("/comparison/periods", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function compareCohorts(body: CompareCohortsInput): Promise<CohortComparison> {
  return request("/comparison/cohorts", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function compareRuns(body: CompareRunsInput): Promise<RunComparison> {
  return request("/comparison/runs", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function useCompare() {
  return useMutation({
    mutationFn: ({
      mode,
      body,
    }: {
      mode: string;
      body: unknown;
    }): Promise<EntityComparison | PeriodComparison | CohortComparison | RunComparison> => {
      switch (mode) {
        case "videos":
          return compareVideos(body as CompareVideosInput);
        case "channels":
          return compareChannels(body as CompareChannelsInput);
        case "periods":
          return comparePeriods(body as ComparePeriodsInput);
        case "cohorts":
          return compareCohorts(body as CompareCohortsInput);
        case "runs":
          return compareRuns(body as CompareRunsInput);
        default:
          return Promise.reject(new Error(`Unknown comparison mode: ${mode}`));
      }
    },
  });
}

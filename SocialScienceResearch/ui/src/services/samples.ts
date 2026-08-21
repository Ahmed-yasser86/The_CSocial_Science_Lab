"use client";

import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { request, toQuery } from "@/services/api";
import type {
  CreateSampleInput,
  DeleteSampleResult,
  Paginated,
  Sample,
  SampleCompareResult,
} from "@/lib/sample-types";

export const sampleKeys = {
  list: () => ["samples"] as const,
  detail: (sampleId: string) => ["samples", sampleId] as const,
  compare: (sampleIds: string[]) => ["samples", "compare", sampleIds] as const,
};

export function createSample(body: CreateSampleInput): Promise<Sample> {
  return request("/samples", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listSamples(cursor?: string): Promise<Paginated<Sample>> {
  return request(`/samples${toQuery({ cursor })}`);
}

export function getSample(sampleId: string): Promise<Sample> {
  return request(`/samples/${sampleId}`);
}

export function getSampleMembers(
  sampleId: string,
  cursor?: string,
): Promise<Paginated<string>> {
  return request(`/samples/${sampleId}/members${toQuery({ cursor })}`);
}

export function deleteSample(sampleId: string): Promise<DeleteSampleResult> {
  return request(`/samples/${sampleId}`, { method: "DELETE" });
}

export function compareSamples(
  sampleIds: string[],
): Promise<SampleCompareResult> {
  return request("/samples/compare", {
    method: "POST",
    body: JSON.stringify({ sample_ids: sampleIds, metrics: [] }),
  });
}

export function useSampleList() {
  return useInfiniteQuery({
    queryKey: sampleKeys.list(),
    queryFn: ({ pageParam }) => listSamples(pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? (lastPage.next_cursor ?? undefined) : undefined,
  });
}

export function useCreateSample() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateSampleInput) => createSample(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: sampleKeys.list() });
    },
  });
}

export function useDeleteSample() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sampleId: string) => deleteSample(sampleId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: sampleKeys.list() });
    },
  });
}

export function useCompareSamples() {
  return useMutation({
    mutationFn: (sampleIds: string[]) => compareSamples(sampleIds),
  });
}

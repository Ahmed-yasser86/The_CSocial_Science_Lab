"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { request, toQuery } from "@/services/api";
import { useJob } from "@/services/queries";
import type { Paginated } from "@/lib/network-full-types";
import type {
  ExpansionActionPayload,
  ExpansionGraphPayload,
  ExpansionStats,
  ScrapeFilters,
} from "@/lib/network-expansion-types";

export const networkExpansionKeys = {
  list: ["network", "expansion", "list"] as const,
  action: (actionId: string) => ["network", "expansion", actionId] as const,
  stats: (actionId: string) => ["network", "expansion", actionId, "stats"] as const,
  graph: (actionId: string, projection: string) =>
    ["network", "expansion", actionId, "graph", projection] as const,
};

function invalidateExpansionQueries(queryClient: ReturnType<typeof useQueryClient>) {
  void queryClient.invalidateQueries({ queryKey: ["network", "expansion"] });
  void queryClient.invalidateQueries({ queryKey: ["network", "graph"] });
  void queryClient.invalidateQueries({ queryKey: ["network", "videos"] });
  void queryClient.invalidateQueries({ queryKey: ["network", "summary"] });
  // The video-page Recommendations tab and per-video metadata also change once
  // new recommendation edges land for a scraped video.
  void queryClient.invalidateQueries({ queryKey: ["videos"] });
  void queryClient.invalidateQueries({ queryKey: ["runs"] });
  void queryClient.invalidateQueries({ queryKey: ["jobs"] });
  void queryClient.invalidateQueries({ queryKey: ["projects"] });
}

export function getExpansions(): Promise<ExpansionActionPayload[]> {
  return request<Paginated<ExpansionActionPayload>>("/network/expansion").then(
    (page) => page.items ?? [],
  );
}

export function getExpansion(actionId: string): Promise<ExpansionActionPayload> {
  return request(`/network/expansion/${actionId}`);
}

export function getExpansionStats(actionId: string): Promise<ExpansionStats> {
  return request(`/network/expansion/${actionId}/stats`);
}

export function getExpansionGraph(
  actionId: string,
  projection: "video" | "channel" = "video",
): Promise<ExpansionGraphPayload> {
  return request(
    `/network/expansion/${actionId}/graph${toQuery({ projection })}`,
  );
}

export function scrapeExpansionVideo(
  videoId: string,
  filters: ScrapeFilters,
): Promise<{ job_id: string }> {
  return request("/network/expansion/scrape-video", {
    method: "POST",
    body: JSON.stringify({ video_id: videoId, filters }),
  });
}

export function scrapeExpansionAll(
  body: { run_id?: string | null; video_ids?: string[]; filters: ScrapeFilters },
): Promise<{ job_id: string }> {
  return request("/network/expansion/scrape-all", {
    method: "POST",
    body: JSON.stringify({
      run_id: body.run_id ?? null,
      video_ids: body.video_ids ?? [],
      filters: body.filters,
    }),
  });
}

export function useExpansions() {
  return useQuery({
    queryKey: networkExpansionKeys.list,
    queryFn: getExpansions,
  });
}

export function useExpansion(actionId: string | null) {
  return useQuery({
    queryKey: networkExpansionKeys.action(actionId ?? ""),
    queryFn: () => getExpansion(actionId as string),
    enabled: !!actionId,
  });
}

export function useExpansionStats(actionId: string | null) {
  return useQuery({
    queryKey: networkExpansionKeys.stats(actionId ?? ""),
    queryFn: () => getExpansionStats(actionId as string),
    enabled: !!actionId,
  });
}

export function useExpansionGraph(actionId: string | null, projection: string) {
  return useQuery({
    queryKey: networkExpansionKeys.graph(actionId ?? "", projection),
    queryFn: () =>
      getExpansionGraph(actionId as string, projection as "video" | "channel"),
    enabled: !!actionId,
  });
}

/** Submit + poll a job; invalidate network/expansion/project queries on success. */
export function useExpansionJob() {
  const queryClient = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);
  const jobQuery = useJob(jobId);
  const status = jobQuery.data?.status;

  useEffect(() => {
    if (status === "succeeded") {
      invalidateExpansionQueries(queryClient);
    }
  }, [status, queryClient]);

  const mutation = useMutation({
    mutationFn: (fn: () => Promise<{ job_id: string }>) => fn(),
    onSuccess: (data) => setJobId(data.job_id),
  });

  return {
    ...mutation,
    jobId,
    job: jobQuery.data,
    isRunning:
      jobId !== null &&
      (jobQuery.data?.status === "pending" || jobQuery.data?.status === "running"),
  };
}

"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useJob } from "@/services/queries";
import { request, toQuery } from "@/services/api";
import type {
  ChannelGraphPayload,
  ChannelProjection,
  EdgeRow,
  GraphProjection,
  NetworkExportFormat,
  NetworkGraphPayload,
  NetworkMetrics,
  Paginated,
  TemporalResult,
} from "@/lib/network-full-types";

export const networkFullKeys = {
  metrics: (runId?: string, topN = 10) =>
    ["network", "full", "metrics", runId ?? "all", topN] as const,
  temporal: (runs: string[]) =>
    ["network", "full", "temporal", runs.join(",")] as const,
  edges: (runId?: string, cursor?: string) =>
    ["network", "full", "edges", runId ?? "all", cursor ?? "start"] as const,
  channels: (runId?: string) =>
    ["network", "full", "channels", runId ?? "all"] as const,
  graph: (
    runId?: string,
    channelId?: string,
    channelScope?: string,
    projection: GraphProjection = "video",
    layerIndex?: number,
    connected?: string,
    scraped?: string,
  ) =>
    [
      "network",
      "graph",
      runId ?? "all",
      channelId ?? "all",
      channelScope ?? "source",
      projection,
      layerIndex ?? "all",
      connected ?? "all",
      scraped ?? "all",
    ] as const,
};

export function getNetworkMetrics(
  runId?: string,
  topN = 10,
): Promise<NetworkMetrics> {
  return request(
    `/network/metrics${toQuery({ run_id: runId, top_n: topN })}`,
  );
}

export function getNetworkTemporal(runs: string[]): Promise<TemporalResult> {
  return request(
    `/network/temporal${toQuery({ runs: runs.join(",") })}`,
  );
}

export function getNetworkEdges(
  runId?: string,
  cursor?: string,
): Promise<Paginated<EdgeRow>> {
  return request(
    `/network/edges${toQuery({ run_id: runId, cursor })}`,
  );
}

export function getChannelProjection(
  runId?: string,
): Promise<ChannelProjection> {
  return request(
    `/network/channels${toQuery({ run_id: runId })}`,
  );
}

export function getNetworkExportUrl(
  format: NetworkExportFormat,
  runId?: string,
): string {
  const base =
    process.env.NEXT_PUBLIC_API_URL ?? "/api/v1/social-science";
  return `${base}/network/export${toQuery({ format, run_id: runId })}`;
}

export function useNetworkMetrics(runId?: string, topN = 10, options = {}) {
  return useQuery({
    queryKey: networkFullKeys.metrics(runId, topN),
    queryFn: () => getNetworkMetrics(runId, topN),
    retry: 1,
    ...options,
  });
}

export function useNetworkTemporal(runs: string[]) {
  return useQuery({
    queryKey: networkFullKeys.temporal(runs),
    queryFn: () => getNetworkTemporal(runs),
    enabled: runs.length > 0,
  });
}

export function useNetworkEdges(runId?: string, cursor?: string) {
  return useQuery({
    queryKey: networkFullKeys.edges(runId, cursor),
    queryFn: () => getNetworkEdges(runId, cursor),
    placeholderData: (previous) => previous,
    staleTime: 30_000,
  });
}

export function useChannelProjection(runId?: string) {
  return useQuery({
    queryKey: networkFullKeys.channels(runId),
    queryFn: () => getChannelProjection(runId),
  });
}

export function getNetworkGraph(
  runId?: string,
  channelId?: string,
  channelScope?: "source" | "target" | "either",
  projection: GraphProjection = "video",
  layerIndex?: number,
  connected?: "only" | "isolated",
  scraped?: "scraped" | "unscraped",
): Promise<NetworkGraphPayload | ChannelGraphPayload> {
  return request(
    `/network/graph${toQuery({
      run_id: runId,
      channel_id: channelId,
      channel_scope: channelScope,
      projection,
      layer_index: layerIndex,
      connected,
      scraped,
    })}`,
  );
}

export function useNetworkGraph(
  runId?: string,
  channelId?: string,
  channelScope: "source" | "target" | "either" = "source",
  projection: GraphProjection = "video",
  options = {},
  layerIndex?: number,
  connected?: "only" | "isolated",
  scraped?: "scraped" | "unscraped",
) {
  return useQuery({
    queryKey: networkFullKeys.graph(
      runId,
      channelId,
      channelScope,
      projection,
      layerIndex,
      connected,
      scraped,
    ),
    queryFn: () =>
      getNetworkGraph(
        runId,
        channelId,
        channelScope,
        projection,
        layerIndex,
        connected,
        scraped,
      ),
    placeholderData: (previous) => previous,
    ...options,
  });
}

export type ScrapeKind = "video" | "run" | "channel";

export function scrapeNetwork(kind: ScrapeKind, body: Record<string, unknown>): Promise<{ job_id: string }> {
  return request(`/network/scrape/${kind}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function useScrapeNetwork(kind: ScrapeKind) {
  const queryClient = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);
  const jobQuery = useJob(jobId);
  const status = jobQuery.data?.status;

  useEffect(() => {
    if (status === "succeeded" || status === "failed") {
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["network", "summary"] });
      void queryClient.invalidateQueries({ queryKey: ["network", "graph"] });
      void queryClient.invalidateQueries({ queryKey: ["network", "full"] });
      void queryClient.invalidateQueries({ queryKey: ["network", "videos"] });
      void queryClient.invalidateQueries({ queryKey: ["runs"] });
    }
  }, [status, queryClient]);

  const mutation = useMutation({
    mutationFn: (body: Record<string, unknown>) => scrapeNetwork(kind, body),
    onSuccess: (data) => setJobId(data.job_id),
  });

  return {
    ...mutation,
    jobId,
    job: jobQuery.data,
    isRunning:
      jobId !== null &&
      (jobQuery.data?.status === "pending" ||
        jobQuery.data?.status === "running"),
  };
}

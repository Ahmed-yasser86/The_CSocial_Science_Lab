"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useJob } from "@/services/queries";
import { request, toQuery } from "@/services/api";
import type {
  ChannelGraphPayload,
  ChannelProjection,
  CommenterCommunityInsights,
  CommenterNetworkGraph,
  CommenterNetworkMetrics,
  CommenterProjection,
  CommunityInsights,
  EdgeRow,
  GraphProjection,
  NetworkCentralities,
  NetworkExportFormat,
  NetworkGraphPayload,
  NetworkMetrics,
  NetworkRoles,
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
    channelIds?: string[],
    videoIds?: string[],
    channelScope?: string,
    projection: GraphProjection = "video",
    layerIndex?: number,
    connected?: string,
    scraped?: string,
    includeSubRuns?: boolean,
    jobIds?: string[],
  ) =>
    [
      "network",
      "graph",
      runId ?? "all",
      (channelIds ?? []).join(",") || "all",
      (videoIds ?? []).join(",") || "all",
      channelScope ?? "source",
      projection,
      layerIndex ?? "all",
      connected ?? "all",
      scraped ?? "all",
      includeSubRuns ? "subruns" : "single",
      (jobIds ?? []).join(",") || "all",
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

export interface NetworkMatricesResponse {
  community_matrix: {
    labels: string[];
    matrix: Record<string, Record<string, number>>;
    totals: Record<string, number>;
    label_meta: Record<string, string>;
  };
  layer_matrix: {
    labels: number[];
    rows: Array<{
      layer_index: number;
      edge_count: number;
      unique_sources: number;
      unique_targets: number;
      unique_target_channels: number;
    }>;
  };
}

export function getNetworkMatrices(
  channelIds?: string[],
  runIds?: string[],
): Promise<NetworkMatricesResponse> {
  return request(
    `/network/matrices${toQuery({
      channel_ids: channelIds?.join(","),
      run_ids: runIds?.join(","),
    })}`,
  );
}

export function useNetworkMatrices(channelIds?: string[], runIds?: string[]) {
  return useQuery({
    queryKey: [
      "network",
      "full",
      "matrices",
      (channelIds ?? []).join(","),
      (runIds ?? []).join(","),
    ] as const,
    queryFn: () => getNetworkMatrices(channelIds, runIds),
    retry: 1,
  });
}

export interface SamplingFeasibilityResponse {
  entity_type: string;
  population_size: number;
  available_metric: number;
  missing_metric: number;
  coverage: number | null;
  requested_size: number | null;
  max_sample_size: number;
  recommended_sample_size: number;
}

export function getSamplingFeasibility(params: {
  entity_type: string;
  channel_id?: string;
  run_ids?: string[];
  metric?: string;
  requested_size?: number;
}): Promise<SamplingFeasibilityResponse> {
  return request(
    `/network/sampling-feasibility${toQuery({
      entity_type: params.entity_type,
      channel_id: params.channel_id,
      run_ids: params.run_ids?.join(","),
      metric: params.metric,
      requested_size: params.requested_size,
    })}`,
  );
}

export function useSamplingFeasibility(params: {
  entity_type: string;
  channel_id?: string;
  run_ids?: string[];
  metric?: string;
  requested_size?: number;
}) {
  return useQuery({
    queryKey: [
      "network",
      "sampling-feasibility",
      params.entity_type,
      params.channel_id ?? "all",
      (params.run_ids ?? []).join(","),
      params.metric ?? "all",
      params.requested_size ?? "none",
    ] as const,
    queryFn: () => getSamplingFeasibility(params),
    retry: 1,
  });
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

export function getNetworkCentralities(
  params: {
    run_id?: string;
    channel_id?: string;
    channel_ids?: string[];
    channel_scope?: string;
    layer_index?: number;
    video_ids?: string[];
    projection?: GraphProjection;
  } = {},
): Promise<NetworkCentralities> {
  return request(
    `/network/centralities${toQuery({
      run_id: params.run_id,
      channel_id: params.channel_id,
      channel_ids: params.channel_ids?.join(","),
      channel_scope: params.channel_scope,
      layer_index: params.layer_index,
      video_ids: params.video_ids?.join(","),
      projection: params.projection,
    })}`,
  );
}

export function useNetworkCentralities(
  params: {
    run_id?: string;
    channel_id?: string;
    channel_ids?: string[];
    channel_scope?: string;
    layer_index?: number;
    video_ids?: string[];
    projection?: GraphProjection;
    enabled?: boolean;
  } = {},
) {
  return useQuery({
    queryKey: [
      "network",
      "full",
      "centralities",
      params.run_id ?? "all",
      params.channel_id ?? "all",
      (params.channel_ids ?? []).join(",") || "all",
      params.channel_scope ?? "source",
      params.layer_index ?? "all",
      (params.video_ids ?? []).join(",") || "all",
      params.projection ?? "video",
    ] as const,
    queryFn: () => getNetworkCentralities(params),
    enabled: params.enabled ?? true,
    retry: 1,
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
  channelIds?: string[],
  videoIds?: string[],
  channelScope?: "source" | "target" | "either",
  projection: GraphProjection = "video",
  layerIndex?: number,
  connected?: "only" | "isolated",
  scraped?: "scraped" | "unscraped",
  includeSubRuns?: boolean,
  jobIds?: string[],
): Promise<NetworkGraphPayload | ChannelGraphPayload> {
  return request(
    `/network/graph${toQuery({
      run_id: runId,
      channel_ids: channelIds?.length ? channelIds.join(",") : undefined,
      video_ids: videoIds?.length ? videoIds.join(",") : undefined,
      channel_scope: channelScope,
      projection,
      layer_index: layerIndex,
      connected,
      scraped,
      include_sub_runs: includeSubRuns ? "true" : undefined,
      job_ids: jobIds?.length ? jobIds.join(",") : undefined,
    })}`,
  );
}

export function useNetworkGraph(
  runId?: string,
  channelIds?: string[],
  videoIds?: string[],
  channelScope: "source" | "target" | "either" = "source",
  projection: GraphProjection = "video",
  options = {},
  layerIndex?: number,
  connected?: "only" | "isolated",
  scraped?: "scraped" | "unscraped",
  includeSubRuns?: boolean,
  jobIds?: string[],
) {
  return useQuery({
    queryKey: networkFullKeys.graph(
      runId,
      channelIds,
      videoIds,
      channelScope,
      projection,
      layerIndex,
      connected,
      scraped,
      includeSubRuns,
      jobIds,
    ),
    queryFn: () =>
      getNetworkGraph(
        runId,
        channelIds,
        videoIds,
        channelScope,
        projection,
        layerIndex,
        connected,
        scraped,
        includeSubRuns,
        jobIds,
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

// ---------------------------------------------------------------------------
// Audience (commenter) network family -- N2 / WS7
// ---------------------------------------------------------------------------
export interface CommenterNetworkParams {
  runId?: string | null;
  videoIds?: string[];
  channelIds?: string[];
  projection?: CommenterProjection;
  weight?: string;
  minShared?: number;
  topN?: number;
  weighted?: boolean;
}

export function getCommenterNetworkGraph(
  params: CommenterNetworkParams = {},
): Promise<CommenterNetworkGraph> {
  return request(
    `/network/commenters/graph${toQuery({
      run_ids: params.runId ? params.runId : undefined,
      video_ids: params.videoIds?.join(","),
      channel_ids: params.channelIds?.join(","),
      projection: params.projection,
      weight: params.weight,
      min_shared: params.minShared,
      top_n: params.topN,
      weighted: params.weighted,
    })}`,
  );
}

export function useCommenterNetworkGraph(
  params: CommenterNetworkParams & { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: [
      "network",
      "commenters",
      "graph",
      params.runId ?? "all",
      (params.videoIds ?? []).join(",") || "all",
      (params.channelIds ?? []).join(",") || "all",
      params.projection ?? "commenter",
      params.weight ?? "co_comment:jaccard",
      params.minShared ?? "all",
      params.topN ?? "all",
      params.weighted ?? true,
    ] as const,
    queryFn: () => getCommenterNetworkGraph(params),
    enabled: params.enabled ?? true,
    retry: 1,
  });
}

export function getCommenterNetworkMetrics(
  params: CommenterNetworkParams = {},
): Promise<CommenterNetworkMetrics> {
  return request(
    `/network/commenters/metrics${toQuery({
      run_ids: params.runId ? params.runId : undefined,
      video_ids: params.videoIds?.join(","),
      channel_ids: params.channelIds?.join(","),
      projection: params.projection,
      weight: params.weight,
      min_shared: params.minShared,
      top_n: params.topN,
      weighted: params.weighted,
    })}`,
  );
}

export function useCommenterNetworkMetrics(
  params: CommenterNetworkParams & { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: [
      "network",
      "commenters",
      "metrics",
      params.runId ?? "all",
      (params.videoIds ?? []).join(",") || "all",
      (params.channelIds ?? []).join(",") || "all",
      params.projection ?? "commenter",
      params.weight ?? "co_comment:jaccard",
      params.minShared ?? "all",
      params.topN ?? "all",
      params.weighted ?? true,
    ] as const,
    queryFn: () => getCommenterNetworkMetrics(params),
    enabled: params.enabled ?? true,
    retry: 1,
  });
}

export function getCommenterNetworkExportUrl(
  params: CommenterNetworkParams & { format?: NetworkExportFormat } = {},
): string {
  const q = toQuery({
    run_ids: params.runId ? params.runId : undefined,
    video_ids: params.videoIds?.join(","),
    channel_ids: params.channelIds?.join(","),
    projection: params.projection,
    weight: params.weight,
    min_shared: params.minShared,
    top_n: params.topN,
    weighted: params.weighted,
    format: params.format ?? "graphml",
  });
  return `/network/commenters/export${q}`;
}

// ---------------------------------------------------------------------------
// Structural roles + community insights (N3)
// ---------------------------------------------------------------------------
export interface NetworkScopeParams {
  runId?: string;
  channelId?: string;
  channelIds?: string[];
  channelScope?: string;
  layerIndex?: number;
  videoIds?: string[];
  projection?: GraphProjection;
  weight?: string;
  weighted?: boolean;
  roleModel?: string;
}

function networkScopeQuery(params: NetworkScopeParams) {
  return toQuery({
    run_id: params.runId,
    channel_id: params.channelId,
    channel_ids: params.channelIds?.join(","),
    channel_scope: params.channelScope,
    layer_index: params.layerIndex,
    video_ids: params.videoIds?.join(","),
    projection: params.projection,
    weight: params.weight,
    weighted: params.weighted,
    role_model: params.roleModel,
  });
}

export function getNetworkRoles(
  params: NetworkScopeParams = {},
): Promise<NetworkRoles> {
  return request(`/network/roles${networkScopeQuery(params)}`);
}

export function useNetworkRoles(
  params: NetworkScopeParams & { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: [
      "network",
      "full",
      "roles",
      params.runId ?? "all",
      params.channelId ?? "all",
      (params.channelIds ?? []).join(",") || "all",
      params.channelScope ?? "source",
      params.layerIndex ?? "all",
      (params.videoIds ?? []).join(",") || "all",
      params.projection ?? "video",
      params.weight ?? "all",
      params.roleModel ?? "core_broker_periphery_bridge",
    ] as const,
    queryFn: () => getNetworkRoles(params),
    enabled: params.enabled ?? true,
    retry: 1,
  });
}

export function getNetworkCommunityInsights(
  params: NetworkScopeParams = {},
): Promise<CommunityInsights> {
  return request(`/network/community-insights${networkScopeQuery(params)}`);
}

export function useNetworkCommunityInsights(
  params: NetworkScopeParams & { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: [
      "network",
      "full",
      "community-insights",
      params.runId ?? "all",
      params.channelId ?? "all",
      (params.channelIds ?? []).join(",") || "all",
      params.channelScope ?? "source",
      params.layerIndex ?? "all",
      (params.videoIds ?? []).join(",") || "all",
      params.projection ?? "video",
      params.weight ?? "all",
    ] as const,
    queryFn: () => getNetworkCommunityInsights(params),
    enabled: params.enabled ?? true,
    retry: 1,
  });
}

export function getCommenterNetworkRoles(
  params: CommenterNetworkParams = {},
): Promise<NetworkRoles> {
  return request(
    `/network/commenters/roles${toQuery({
      run_ids: params.runId ? params.runId : undefined,
      video_ids: params.videoIds?.join(","),
      channel_ids: params.channelIds?.join(","),
      projection: params.projection,
      weight: params.weight,
      min_shared: params.minShared,
      top_n: params.topN,
      weighted: params.weighted,
    })}`,
  );
}

export function useCommenterNetworkRoles(
  params: CommenterNetworkParams & { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: [
      "network",
      "commenters",
      "roles",
      params.runId ?? "all",
      (params.videoIds ?? []).join(",") || "all",
      (params.channelIds ?? []).join(",") || "all",
      params.projection ?? "commenter",
      params.weight ?? "co_comment:jaccard",
      params.minShared ?? "all",
      params.topN ?? "all",
    ] as const,
    queryFn: () => getCommenterNetworkRoles(params),
    enabled: params.enabled ?? true,
    retry: 1,
  });
}

export function getCommenterNetworkCommunityInsights(
  params: CommenterNetworkParams = {},
): Promise<CommenterCommunityInsights> {
  return request(
    `/network/commenters/community-insights${toQuery({
      run_ids: params.runId ? params.runId : undefined,
      video_ids: params.videoIds?.join(","),
      channel_ids: params.channelIds?.join(","),
      projection: params.projection,
      weight: params.weight,
      min_shared: params.minShared,
      top_n: params.topN,
      weighted: params.weighted,
    })}`,
  );
}

export function useCommenterNetworkCommunityInsights(
  params: CommenterNetworkParams & { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: [
      "network",
      "commenters",
      "community-insights",
      params.runId ?? "all",
      (params.videoIds ?? []).join(",") || "all",
      (params.channelIds ?? []).join(",") || "all",
      params.projection ?? "commenter",
      params.weight ?? "co_comment:jaccard",
      params.minShared ?? "all",
      params.topN ?? "all",
    ] as const,
    queryFn: () => getCommenterNetworkCommunityInsights(params),
    enabled: params.enabled ?? true,
    retry: 1,
  });
}

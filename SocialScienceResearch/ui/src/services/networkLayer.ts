"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { request, toQuery } from "@/services/api";
import { useJob } from "@/services/queries";
import type { Paginated } from "@/lib/network-full-types";
import type {
  ChannelGraphPayload,
  LayerFrontier,
  LayerProjection,
  LayerRun,
  NewRelationsReport,
} from "@/lib/network-layer-types";

export const networkLayerKeys = {
  layers: ["network", "layer", "list"] as const,
  layer: (layerRunId: string) =>
    ["network", "layer", layerRunId] as const,
  relations: (layerRunId: string) =>
    ["network", "layer", layerRunId, "relations"] as const,
  graph: (layerRunId: string, projection: LayerProjection) =>
    ["network", "layer", layerRunId, "graph", projection] as const,
  frontier: (layerRunId: string) =>
    ["network", "layer", layerRunId, "frontier"] as const,
};

function invalidateLayerQueries(queryClient: ReturnType<typeof useQueryClient>) {
  void queryClient.invalidateQueries({ queryKey: ["network", "layer"] });
  void queryClient.invalidateQueries({ queryKey: ["network", "graph"] });
  void queryClient.invalidateQueries({ queryKey: ["network", "full"] });
  void queryClient.invalidateQueries({ queryKey: ["network", "summary"] });
  void queryClient.invalidateQueries({ queryKey: ["runs"] });
  void queryClient.invalidateQueries({ queryKey: ["jobs"] });
}

export function getLayers(): Promise<LayerRun[]> {
  return request<Paginated<LayerRun>>("/network/layers").then(
    (page) => page.items ?? [],
  );
}

export function getLayer(layerRunId: string): Promise<LayerRun> {
  return request(`/network/layer/${layerRunId}`);
}

export function getLayerRelations(layerRunId: string): Promise<NewRelationsReport> {
  return request(`/network/layer/${layerRunId}/relations`);
}

export function getLayerGraph(
  layerRunId: string,
  projection: LayerProjection,
): Promise<ChannelGraphPayload> {
  return request(
    `/network/layer/${layerRunId}/graph${toQuery({ projection })}`,
  );
}

export function getLayerFrontier(layerRunId: string): Promise<LayerFrontier> {
  return request(`/network/layer/${layerRunId}/frontier`);
}

export function bootstrapLayer(
  runId: string,
  projection: LayerProjection = "video",
): Promise<LayerRun> {
  return request("/network/layer", {
    method: "POST",
    body: JSON.stringify({ run_id: runId, projection }),
  });
}

export function crawlNextLayer(body: {
  parent_layer_run_id?: string;
  parent_run_id?: string;
  projection?: LayerProjection;
  collect_comments?: boolean;
  concurrency?: number;
}): Promise<{ job_id: string }> {
  return request("/network/layer/scrape", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function useLayers() {
  return useQuery({
    queryKey: networkLayerKeys.layers,
    queryFn: getLayers,
  });
}

export function useLayer(layerRunId: string | null) {
  return useQuery({
    queryKey: networkLayerKeys.layer(layerRunId ?? ""),
    queryFn: () => getLayer(layerRunId as string),
    enabled: !!layerRunId,
  });
}

export function useLayerRelations(layerRunId: string | null) {
  return useQuery({
    queryKey: networkLayerKeys.relations(layerRunId ?? ""),
    queryFn: () => getLayerRelations(layerRunId as string),
    enabled: !!layerRunId,
  });
}

export function useLayerGraph(
  layerRunId: string | null,
  projection: LayerProjection,
) {
  return useQuery({
    queryKey: networkLayerKeys.graph(layerRunId ?? "", projection),
    queryFn: () => getLayerGraph(layerRunId as string, projection),
    enabled: !!layerRunId,
  });
}

export function useLayerFrontier(layerRunId: string | null) {
  return useQuery({
    queryKey: networkLayerKeys.frontier(layerRunId ?? ""),
    queryFn: () => getLayerFrontier(layerRunId as string),
    enabled: !!layerRunId,
  });
}

export function useBootstrapLayer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ runId, projection }: { runId: string; projection: LayerProjection }) =>
      bootstrapLayer(runId, projection),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["network", "layer"] });
    },
  });
}

/** Submit + poll a crawl job; invalidate layer/graph/runs on terminal state. */
export function useCrawlNextLayer() {
  const queryClient = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);
  const jobQuery = useJob(jobId);
  const status = jobQuery.data?.status;

  useEffect(() => {
    if (status === "succeeded") {
      invalidateLayerQueries(queryClient);
    }
  }, [status, queryClient]);

  const mutation = useMutation({
    mutationFn: (body: Parameters<typeof crawlNextLayer>[0]) => crawlNextLayer(body),
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

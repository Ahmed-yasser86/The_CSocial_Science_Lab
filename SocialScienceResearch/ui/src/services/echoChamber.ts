"use client";

import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { request, toQuery } from "@/services/api";
import type {
  EchoAudience,
  EchoDetection,
  EchoLayerSnapshot,
  EchoLens,
  EchoProjection,
  EchoStructure,
} from "@/lib/echo-chamber";
import { isTerminalDetection } from "@/lib/echo-chamber";

/**
 * Echo-chamber detector service hooks (echo plan E2).
 *
 * The detection endpoint is the source of truth for the layered timeline;
 * while a detection is pending/running the status query polls (pitfall A2
 * fallback — SSE exists for the underlying job via <JobProgressCard>, the
 * timeline itself is poll-based).
 */

export const echoChamberKeys = {
  detection: (detectionId: string | null) =>
    ["echo-chamber", detectionId ?? "none"] as const,
  list: ["echo-chamber", "list"] as const,
  lens: (detectionId: string | null, projection: EchoProjection) =>
    ["echo-chamber", detectionId ?? "none", "lens", projection] as const,
};

export interface DetectEchoBody {
  video_url?: string;
  video_id?: string;
  seed_run_id?: string;
  max_layers?: number;
  collect_comments?: boolean;
  projection?: "video" | "channel";
}

export function detectEchoChamber(
  body: DetectEchoBody,
): Promise<{ detection_id: string; job_id: string | null; status: string }> {
  return request("/echo-chamber/detect", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getEchoDetection(detectionId: string): Promise<EchoDetection> {
  return request(`/echo-chamber/${encodeURIComponent(detectionId)}`);
}

export function continueEchoChamber(
  detectionId: string,
  extraLayers: number,
): Promise<{ job_id: string | null }> {
  return request(`/echo-chamber/${encodeURIComponent(detectionId)}/continue`, {
    method: "POST",
    body: JSON.stringify({ extra_layers: extraLayers }),
  });
}

export function stopEchoChamber(
  detectionId: string,
): Promise<{ detection_id: string; job_id: string | null; status: string }> {
  return request(`/echo-chamber/${encodeURIComponent(detectionId)}/stop`, {
    method: "POST",
  });
}

export function listEchoDetections(cursor?: string): Promise<{
  items: EchoDetection[];
  next_cursor: string | null;
  has_more: boolean;
  total: number;
}> {
  return request(`/echo-chamber${toQuery({ cursor, page_size: 50 })}`);
}

/** Recompute one lens (video | channel) from stored crawl edges on demand. */
export function getEchoLens(
  detectionId: string,
  projection: EchoProjection,
): Promise<EchoLens> {
  return request(
    `/echo-chamber/${encodeURIComponent(detectionId)}/lens${toQuery({
      projection,
    })}`,
  );
}

/** Cached-per-(detection, projection) lens query. */
export function useEchoLens(
  detectionId: string | null,
  projection: EchoProjection,
) {
  return useQuery({
    queryKey: echoChamberKeys.lens(detectionId, projection),
    queryFn: () => getEchoLens(detectionId as string, projection),
    enabled: !!detectionId,
    staleTime: 60_000,
  });
}

/** Full structural analysis (spec §37 sections) from stored crawl edges. */
export function getEchoStructure(detectionId: string): Promise<EchoStructure> {
  return request(
    `/echo-chamber/${encodeURIComponent(detectionId)}/structure`,
  );
}

export function useEchoStructure(detectionId: string | null) {
  return useQuery({
    queryKey: ["echo-chamber", detectionId ?? "none", "structure"],
    queryFn: () => getEchoStructure(detectionId as string),
    enabled: !!detectionId,
    staleTime: 60_000,
    retry: false,
  });
}

/** Audience/commenter lens (spec §22): Jaccard within/between communities. */
export function getEchoAudience(detectionId: string): Promise<EchoAudience> {
  return request(
    `/echo-chamber/${encodeURIComponent(detectionId)}/audience`,
  );
}

export function useEchoAudience(detectionId: string | null) {
  return useQuery({
    queryKey: ["echo-chamber", detectionId ?? "none", "audience"],
    queryFn: () => getEchoAudience(detectionId as string),
    enabled: !!detectionId,
    staleTime: 60_000,
    retry: false,
  });
}

/** Poll a detection until terminal; keeps the live progress card in sync. */
export function useEchoDetection(detectionId: string | null) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: echoChamberKeys.detection(detectionId),
    queryFn: () => getEchoDetection(detectionId as string),
    enabled: !!detectionId,
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      return isTerminalDetection(status ?? "") ? false : 2000;
    },
  });

  // Terminal-event client invalidation (R1 end-to-end, pitfall A3: effect
  // keyed on status, never render-time): a finished echo crawl appended
  // layers/edges, so graph/metrics/layers/runs queries are stale until
  // invalidated.
  const status = query.data?.status;
  useEffect(() => {
    if (detectionId && status && isTerminalDetection(status)) {
      void queryClient.invalidateQueries({ queryKey: ["network"] });
      void queryClient.invalidateQueries({ queryKey: ["runs"] });
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
    }
  }, [detectionId, status, queryClient]);

  return query;
}

export type { EchoLayerSnapshot };

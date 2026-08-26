"use client";

import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { request, toQuery } from "@/services/api";

/**
 * Content Homophily service hooks (Content Homophily spec §22-§24).
 *
 * Opt-in, on-demand CONTENT evidence: the start endpoint queues ONE job that
 * does targeted transcript collection -> embeddings -> seeded pair sampling ->
 * permutation null. While the analysis is pending/running the record query
 * polls (pitfall A2 fallback discipline — poll-based like the echo timeline).
 */

export const CONTENT_HOMOPHILY_STAGES = [
  "dataset_preparation",
  "transcript_collection",
  "embedding_preparation",
  "pair_sampling",
  "similarity_calculation",
  "observed_difference",
  "null_model",
  "statistical_summary",
  "results",
] as const;

export type ContentHomophilyStage = (typeof CONTENT_HOMOPHILY_STAGES)[number];

export const STAGE_LABELS: Record<ContentHomophilyStage, string> = {
  dataset_preparation: "1. Dataset Preparation",
  transcript_collection: "2. Transcript Collection",
  embedding_preparation: "3. Embedding Preparation",
  pair_sampling: "4. Pair Sampling",
  similarity_calculation: "5. Similarity Calculation",
  observed_difference: "6. Observed Difference",
  null_model: "7. Null Model",
  statistical_summary: "8. Statistical Summary",
  results: "9. Results",
};

export interface ContentHomophilyProgress {
  current_stage: string | null;
  stages: Partial<Record<ContentHomophilyStage, string>>;
  log: { ts: string; message: string }[];
  videos_total?: number;
  videos_processed?: number;
  current_video?: string;
  embeddings_reused?: number;
  embeddings_generated?: number;
  embedding_failures?: number;
  embedding_model?: string;
  null_permutations_done?: number;
  elapsed_seconds?: number;
  eta_seconds?: number | null;
}

export interface ContentHomophilyResults {
  status: string;
  label?: string;
  reason?: string;
  within_mean_similarity: number | null;
  between_mean_similarity: number | null;
  observed_difference: number | null;
  null_mean: number | null;
  null_std: number | null;
  z_score: number | null;
  permutation_p_value: number | null;
  pairs_available_within: number;
  pairs_sampled_within: number;
  pairs_available_between: number;
  pairs_sampled_between: number;
  sampling_fraction: number;
  max_pair_cap: number;
  random_seed: number;
  num_permutations: number;
  videos_with_transcript: number;
  videos_without_transcript: number;
  transcript_coverage: number;
  embedding_model: string;
  embedding_model_version: string;
  embeddings_reused?: number;
  embeddings_generated?: number;
  embedding_failures?: number;
  analysis_run_id: string;
  community_algorithm?: string;
  chunking_configuration?: Record<string, unknown>;
  edge_similarity?: {
    mean_edge_semantic_similarity: number | null;
    edges_available: number;
    edges_sampled: number;
    note: string;
  };
  disclaimers: string[];
}

export interface ContentHomophilyRecord {
  analysis_id: string;
  job_id: string | null;
  status:
    | "pending"
    | "running"
    | "observed"
    | "insufficient_data"
    | "stopped"
    | "failed";
  params: Record<string, unknown>;
  progress: ContentHomophilyProgress;
  results?: ContentHomophilyResults;
  error?: string;
  created_at: string;
}

export interface StartContentHomophilyBody {
  run_id?: string;
  video_ids?: string[];
  sampling_fraction?: number;
  max_pair_cap?: number;
  random_seed?: number;
  num_permutations?: number;
  max_videos_per_community?: number;
  include_edge_similarity?: boolean;
  tags?: string[];
}

export function startContentHomophily(
  body: StartContentHomophilyBody,
): Promise<{ analysis_id: string; job_id: string | null; status: string }> {
  return request("/network/content-homophily", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getContentHomophily(
  analysisId: string,
): Promise<ContentHomophilyRecord> {
  return request(
    `/network/content-homophily/${encodeURIComponent(analysisId)}`,
  );
}

export function listContentHomophily(cursor?: string): Promise<{
  items: ContentHomophilyRecord[];
  next_cursor: string | null;
  has_more: boolean;
  total: number;
}> {
  return request(
    `/network/content-homophily${toQuery({ cursor, page_size: 50 })}`,
  );
}

function isTerminal(status: string | undefined): boolean {
  return (
    status === "observed" ||
    status === "insufficient_data" ||
    status === "stopped" ||
    status === "failed"
  );
}

/** Poll a content homophily analysis until terminal. */
export function useContentHomophily(
  analysisId: string | null,
  nonce: number | string = "",
) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["content-homophily", analysisId ?? "none", nonce],
    queryFn: () => getContentHomophily(analysisId as string),
    enabled: !!analysisId,
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      return isTerminal(status ?? "") ? false : 2000;
    },
  });

  const status = query.data?.status;
  useEffect(() => {
    if (analysisId && status && isTerminal(status)) {
      void queryClient.invalidateQueries({ queryKey: ["content-homophily"] });
    }
  }, [analysisId, status, queryClient]);

  return query;
}

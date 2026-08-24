import type { ChannelFacet, RunFacet } from "@/lib/network-full-types";

/** Filter dialog + expansion request payload (backend ScrapeFilters). */
export interface ScrapeFilters {
  max_recommendations_per_video?: number | null;
  collect_comments?: boolean;
  comment_min_likes?: number | null;
  comment_date_from?: string | null;
  comment_date_to?: string | null;
  max_comments_per_video?: number | null;
  dedupe?: boolean;
  only_new_targets?: boolean;
  concurrency?: number | null;
  projection?: string;
}

/** One network-expansion action anchor (GET /network/expansion). */
export interface ExpansionActionPayload {
  action_id: string;
  kind: "video" | "all";
  parent_run_id?: string | null;
  projection: string;
  status: string;
  started_at: string;
  finished_at?: string | null;
  video_ids: string[];
  discovered_video_ids: string[];
  run_ids: string[];
  comments_collected: number;
  summary: Record<string, number>;
  filters: ScrapeFilters;
  project_id?: string | null;
}

export interface ExpansionOverallStats {
  node_count: number;
  edge_count: number;
  channel_count: number;
  source_count: number;
  component_count: number;
  avg_out_degree?: number | null;
  density?: number | null;
  comment_count: number;
}

export interface VideoExpansionStats {
  video_id: string;
  title?: string | null;
  channel_id?: string | null;
  channel_name?: string | null;
  recommendation_count: number;
  in_degree: number;
  new_targets: number;
  new_channels: number;
  new_edges: number;
  comments_collected: number;
}

export interface ExpansionStats {
  action: ExpansionActionPayload;
  overall: ExpansionOverallStats;
  videos: VideoExpansionStats[];
}

/** Graph payload shared by video (NetworkGraphPayload) and channel projections. */
export interface ExpansionGraphPayload {
  projection: "video" | "channel";
  nodes: unknown[];
  edges: unknown[];
  channels: ChannelFacet[];
  runs: RunFacet[];
  node_count: number;
  edge_count: number;
}

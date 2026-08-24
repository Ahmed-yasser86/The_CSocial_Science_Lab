import type { ChannelFacet, RunFacet } from "@/lib/network-full-types";

/** LayerRun anchor returned by GET /network/layer and /network/layers. */
export interface LayerRun {
  layer_run_id: string;
  layer_index: number;
  parent_run_id?: string | null;
  parent_layer_run_id?: string | null;
  projection: string;
  status: string;
  started_at: string;
  finished_at?: string | null;
  frontier_video_ids: string[];
  discovered_video_ids: string[];
  run_ids: string[];
  comments_collected: number;
  summary: Record<string, number>;
  config_json: Record<string, unknown>;
}

export interface LayerFrontier {
  layer_index: number;
  video_ids: string[];
  video_count: number;
}

export interface NewVideoEntry {
  video_id: string;
  title?: string | null;
  channel_id?: string | null;
  channel_name?: string | null;
  thumbnail_url?: string | null;
  classification: string;
}

export interface NewChannelEntry {
  channel_id: string;
  channel_name?: string | null;
  avatar_url?: string | null;
}

export interface ExistingVideoEntry {
  video_id: string;
  title?: string | null;
  channel_id?: string | null;
}

export interface ComponentSummary {
  component_id: string;
  node_count: number;
  edge_count: number;
  touches_channels: string[];
  node_video_ids: string[];
}

export interface SampleEdge {
  source_video_id: string;
  recommended_video_id: string;
  position?: number | null;
  run_id?: string | null;
}

export interface NewRelationsReport {
  layer_run_id: string;
  layer_index: number;
  projection: string;
  generated_at: string;
  counts: Record<string, number>;
  new_videos: NewVideoEntry[];
  existing_videos: ExistingVideoEntry[];
  new_channels: NewChannelEntry[];
  connected_components: ComponentSummary[];
  disconnected_components: ComponentSummary[];
  sample_edges: SampleEdge[];
}

/** Channel-projection graph node (backend ChannelGraphNode). */
export interface ChannelGraphNode {
  channel_id: string;
  channel_name?: string | null;
  avatar_url?: string | null;
  subscriber_count?: number | null;
  video_count: number;
  in_degree: number;
  out_degree: number;
  run_ids: string[];
  run_types: string[];
}

export interface ChannelGraphEdge {
  source: string;
  target: string;
  video_edge_count: number;
  run_ids: string[];
  sample_video_pairs: Array<Record<string, unknown>>;
}

export interface ChannelGraphPayload {
  projection: "channel";
  nodes: ChannelGraphNode[];
  edges: ChannelGraphEdge[];
  channels: ChannelFacet[];
  runs: RunFacet[];
  node_count: number;
  edge_count: number;
  unattributed_edges: number;
}

export type LayerProjection = "video" | "channel";

export const COUNT_LABELS: Record<string, string> = {
  new_videos: "New videos",
  existing_videos_referenced: "Existing videos",
  new_channels: "New channels",
  existing_channels_referenced: "Existing channels",
  new_edges: "New edges",
  edges_connecting_to_existing_nodes: "Edges to existing",
  edges_without_source_channel: "Unattributed edges",
  skipped_edges_duplicate: "Duplicate edges",
  new_components: "New components",
  connected_components: "Connected components",
  comments_collected: "Comments collected",
};

export interface DegreeDistribution {
  min?: number | null;
  max?: number | null;
  mean?: number | null;
  median?: number | null;
  p25?: number | null;
  p75?: number | null;
  p90?: number | null;
  p95?: number | null;
  p99?: number | null;
}

export interface RankedVideo {
  video_id: string;
  score?: number;
  times_recommended?: number;
  outgoing?: number;
}

export interface NetworkMetrics {
  run_id?: string | null;
  node_count: number;
  edge_count: number;
  density: number;
  is_directed: boolean;
  reciprocity: number;
  degree_distribution: Record<string, DegreeDistribution>;
  avg_clustering: number;
  global_clustering: number;
  weakly_connected_components: number;
  largest_component_size: number;
  largest_component_share: number;
  community_count: number;
  modularity?: number | null;
  top_hubs: RankedVideo[];
  top_authorities: RankedVideo[];
  most_recommended: RankedVideo[];
  most_active_sources: RankedVideo[];
}

export interface NetworkSlice {
  run_id: string;
  node_count: number;
  edge_count: number;
  density: number;
  reciprocity: number;
  top_ranked: RankedVideo[];
}

export interface NodeCentrality {
  degree: number;
  closeness: number;
  eigenvector: number;
  betweenness: number;
  community_id: number | null;
}

export interface NetworkCentralities {
  nodes: Record<string, NodeCentrality>;
  algorithm: string;
  computed_at: string;
}

export interface TemporalGrowth {
  from_run_id: string;
  to_run_id: string;
  node_growth: number;
  edge_growth: number;
  density_growth: number;
}

export interface TemporalResult {
  slices: NetworkSlice[];
  growth: TemporalGrowth[];
}

export interface EdgeRow {
  source_video_id: string;
  recommended_video_id: string;
  position?: number | null;
  run_id?: string | null;
  title?: string | null;
  channel_id?: string | null;
}

export interface ChannelProjection {
  channels: string[];
  edge_count: number;
}

export type GraphNodeKind =
  | "source"
  | "target"
  | "both"
  | "other"
  | "commenter"
  | "video"
  | "channel";

/** Enriched graph node from GET /network/graph. */
export interface GraphNode {
  video_id: string;
  title?: string | null;
  channel_id?: string | null;
  channel_name?: string | null;
  thumbnail_url?: string | null;
  views?: number | null;
  likes?: number | null;
  duration?: number | null;
  kind: GraphNodeKind;
  in_degree: number;
  out_degree: number;
  run_ids?: string[];
  run_types?: string[];
  community_id?: number | null;
  recommendations_scraped?: boolean;
}

/** Enriched directed edge from GET /network/graph. */
export interface GraphEdge {
  source: string;
  target: string;
  position?: number | null;
  run_id?: string | null;
  run_type?: string | null;
  run_name?: string | null;
  title?: string | null;
}

export interface ChannelFacet {
  channel_id: string;
  channel_name?: string | null;
}

export interface RunFacet {
  run_id: string;
  run_type?: string | null;
  name?: string | null;
}

export interface NetworkGraphPayload {
  nodes: GraphNode[];
  edges: GraphEdge[];
  runs: RunFacet[];
  channels: ChannelFacet[];
  node_count: number;
  edge_count: number;
}

export interface ChannelGraphNode {
  channel_id: string;
  channel_name?: string | null;
  avatar_url?: string | null;
  subscriber_count?: number | null;
  video_count: number;
  in_degree: number;
  out_degree: number;
  run_ids?: string[];
  run_types?: string[];
}

export interface ChannelGraphEdge {
  source: string;
  target: string;
  video_edge_count: number;
  run_ids?: string[];
  sample_video_pairs?: Array<{
    source_video_id: string;
    recommended_video_id: string;
    position?: number | null;
  }>;
}

export interface ChannelGraphPayload {
  projection: string;
  nodes: ChannelGraphNode[];
  edges: ChannelGraphEdge[];
  channels: ChannelFacet[];
  runs: RunFacet[];
  node_count: number;
  edge_count: number;
  unattributed_edges: number;
}

export type GraphProjection = "video" | "channel";

// ---------------------------------------------------------------------------
// Audience (commenter) network family -- N2 / WS7
// ---------------------------------------------------------------------------
export type CommenterProjection =
  | "commenter"
  | "co_comment_video"
  | "co_comment_channel"
  | "heterogeneous";

export interface CommenterNetworkNode {
  id: string;
  kind: "commenter" | "video" | "channel";
  label?: string | null;
  degree: number;
  community_id?: number | null;
  identity_kind?: string | null;
  comment_count?: number;
}

export interface CommenterNetworkEdge {
  source: string;
  target: string;
  kind: string;
  weight: number;
  relationship_type?: string;
  shared_count?: number | null;
}

export interface CommenterNetworkGraph {
  projection: string;
  nodes: CommenterNetworkNode[];
  edges: CommenterNetworkEdge[];
  node_count: number;
  edge_count: number;
  weight_spec?: Record<string, unknown> | null;
  community_count: number;
  modularity?: number | null;
  computed_at?: string | null;
}

export interface CommenterCentrality {
  degree: number;
  closeness: number;
  eigenvector: number;
  betweenness: number;
  community_id: number;
}

export interface CommenterNetworkCentralities {
  nodes: Record<string, CommenterCentrality>;
  weight_spec?: Record<string, unknown> | null;
  algorithm: string;
  computed_at?: string | null;
}

export interface BridgeRank {
  id: string;
  label?: string | null;
  betweenness: number;
}

export interface CommenterNetworkMetrics {
  node_count: number;
  edge_count: number;
  density: number;
  community_count: number;
  modularity?: number | null;
  weakly_connected_components: number;
  avg_clustering: number;
  top_bridges: BridgeRank[];
  top_core: BridgeRank[];
  top_prolific: BridgeRank[];
  weight_spec?: Record<string, unknown> | null;
}

export interface Paginated<T> {
  items: T[];
  next_cursor: string | null;
  has_more: boolean;
  total: number;
}

export const EXPORT_FORMATS = ["graphml", "edgelist", "gexf", "csv", "json", "xlsx"] as const;
export type NetworkExportFormat = (typeof EXPORT_FORMATS)[number];

export function formatRankedLabel(video: RankedVideo): string {
  return video.video_id;
}

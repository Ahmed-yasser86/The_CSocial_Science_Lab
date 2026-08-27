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
  pagerank: number;
  harmonic: number;
  constraint: number;
  effective_size: number;
  bridging: number;
  clustering: number;
  community_id: number | null;
}

/** All centrality measures exposed by the full battery (N3), in display order. */
export const CENTRALITY_MEASURES: {
  key: keyof NodeCentrality;
  label: string;
  meaning: string;
}[] = [
  { key: "degree", label: "Degree", meaning: "How often a node is connected; popularity in the recommender's eye." },
  { key: "closeness", label: "Closeness", meaning: "How quickly reachable from anywhere; hub reach." },
  { key: "eigenvector", label: "Eigenvector", meaning: "Connected to other well-connected nodes — core of the network space." },
  { key: "betweenness", label: "Betweenness", meaning: "Broker between clusters — funnels viewers across topical silos." },
  { key: "pagerank", label: "PageRank", meaning: "Iterative importance; being recommended by important nodes compounds." },
  { key: "harmonic", label: "Harmonic", meaning: "Closeness variant robust across disconnected components." },
  { key: "constraint", label: "Constraint (Burt)", meaning: "Low constraint = structural-hole spanner with agenda-setting potential." },
  { key: "effective_size", label: "Effective size (Burt)", meaning: "Non-redundant reach of a node's network neighbourhood." },
  { key: "bridging", label: "Bridging", meaning: "Normalised brokerage (betweenness / most central node)." },
  { key: "clustering", label: "Clustering", meaning: "Triadic closure; cohesive vs brokerage neighbourhoods." },
];

export type NetworkRole = "core" | "broker" | "bridge" | "periphery";

export interface NodeRole {
  role: NetworkRole;
  community_id: number | null;
}

export interface NetworkRoles {
  nodes: Record<string, NodeRole>;
  role_model: string;
  approximate?: boolean;
  algorithm: string;
  computed_at: string;
}

export interface CommunityInsight {
  community_id: number;
  size: number;
  dominant_channels: { channel_id: string; count: number }[];
  top_eigenvector: { id: string; label: string | null; value: number }[];
  top_betweenness: { id: string; label: string | null; value: number }[];
}

export interface CommunityInsights {
  communities: CommunityInsight[];
  algorithm: string;
  computed_at: string;
}

export interface NetworkCentralities {
  nodes: Record<string, NodeCentrality>;
  global?: { assortativity?: number | null };
  approximate?: boolean;
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
  weight_spec?: Record<string, unknown> | null;
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
  weight_spec?: Record<string, unknown> | null;
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
  pagerank: number;
  harmonic: number;
  constraint: number;
  effective_size: number;
  bridging: number;
  clustering: number;
  community_id: number;
}

export interface CommenterNetworkCentralities {
  nodes: Record<string, CommenterCentrality>;
  weight_spec?: Record<string, unknown> | null;
  algorithm: string;
  computed_at?: string | null;
}

export interface CommenterCommunityInsight {
  community_id: number;
  size: number;
  dominant_kinds: Record<string, number>;
  top_bridges: { id: string; label?: string | null; betweenness: number }[];
}

export interface CommenterCommunityInsights {
  communities: CommenterCommunityInsight[];
  algorithm: string;
  computed_at: string;
}

/** A detected community as a first-class graph entity (N4): its member node-ids
 * let the UI highlight or isolate it as a sub-graph. */
export interface CommunityEntity {
  id: string;
  community_id: number;
  label: string;
  size: number;
  node_ids: string[];
  top_node_ids: string[];
}

export interface NetworkCommunities {
  communities: CommunityEntity[];
  algorithm: string;
  seed?: number;
  computed_at: string;
}

export type CommenterCommunities = NetworkCommunities;

export interface TestDifferenceScope {
  run_id?: string | null;
  channel_id?: string | null;
  channel_ids?: string[] | null;
  channel_scope?: string;
  layer_index?: number | null;
  video_ids?: string[] | null;
  projection?: string;
  weight?: string | null;
  weighted?: boolean | null;
  run_ids?: string[] | null;
  min_shared?: number | null;
  top_n?: number | null;
}

export interface TestDifferenceRequest {
  family?: string;
  scope_a: TestDifferenceScope;
  scope_b: TestDifferenceScope;
  metric: string;
  statistic?: string;
  method?: string;
  n_iter?: number;
  seed?: number;
}

export interface TestDifferenceResult {
  metric: string;
  statistic: string;
  method: string;
  seed: number;
  n_iter: number;
  n_nodes_a: number;
  n_nodes_b: number;
  statistic_a: number | null;
  statistic_b: number | null;
  observed_delta: number | null;
  p_value: number | null;
  ci95: [number, number] | null;
  note: string | null;
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

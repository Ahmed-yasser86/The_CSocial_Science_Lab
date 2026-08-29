/**
 * Echo-chamber detector: shared types + pure helpers.
 *
 * Mirrors the backend contract (echo_chamber_detector_plan.md §2.2/§4):
 * five observed signals with availability flags, a transparent composite
 * score and honest verdict bands. A missing signal is never rendered as 0 —
 * helpers keep `null` values and expose an availability status instead.
 */

export type EchoSignalStatus = "available" | "unavailable" | "partial";

export interface EchoSignal {
  value: number | null;
  status: EchoSignalStatus;
  detail?: Record<string, unknown>;
}

export interface EchoLayerSignals {
  s1: EchoSignal;
  s2: EchoSignal;
  s3: EchoSignal;
  s4: EchoSignal;
  s5: EchoSignal;
}

export interface EchoLayerSnapshot {
  layer_run_id: string;
  layer_index: number;
  nodes_discovered: number;
  edges_observed: number;
  nodes_total: number | null;
  signals: EchoLayerSignals;
  computed_at: string;
}

export interface EchoScoreComponent {
  key: "s1" | "s2" | "s3" | "s4" | "s5";
  label: string;
  value: number | null;
  /** Spec §27: raw observed component value. */
  value_raw?: number | null;
  /** Spec §27: normalized value on the common [0,1] scale. */
  value_normalized?: number | null;
  /** Nominal researcher weight (spec §26): .35/.30/.20/.15/.15 */
  weight?: number;
  weight_effective: number;
  /** weight_effective x normalized value (spec §37 Custom Research Index). */
  weighted_contribution?: number;
  /** Lens of the component signal (spec §28). */
  lens?: string;
  status: EchoSignalStatus;
}

// NOTE: the composite "strong / weak / moderate" echo-chamber verdict has been
// removed by request — only honest, non-labeling statuses remain.
export type EchoVerdict = "no_chamber_yet" | "inconclusive";

export interface EchoScore {
  value: number | null;
  band: EchoVerdict | null;
  verdict: EchoVerdict;
  components: EchoScoreComponent[];
  computed_at: string | null;
}

export type EchoDetectionStatus =
  | "pending"
  | "running"
  | "completed"
  | "exhausted"
  | "stopped"
  | "unsupported_stop"
  | "failed"
  | string;

export interface EchoDetection {
  detection_id: string;
  seed_video_id: string | null;
  seed_run_id: string | null;
  root_layer_run_id: string | null;
  job_id: string | null;
  status: EchoDetectionStatus;
  params: {
    video_url?: string | null;
    video_id?: string | null;
    max_layers?: number;
    discovery_mode?: string;
    collect_comments?: boolean;
  };
  layers: EchoLayerSnapshot[];
  score: EchoScore | null;
  error: string | null;
  created_at: string | null;
  updated_at: string | null;
}

// ---------------------------------------------------------------------------
// Detection lifecycle status labels (verdict bands removed by request)
// ---------------------------------------------------------------------------

/** Human label of a detection lifecycle status (incl. natural stops). */
export function statusLabel(status: EchoDetectionStatus): string {
  const map: Record<string, string> = {
    pending: "Queued",
    running: "Crawling",
    completed: "Completed",
    exhausted: "Frontier exhausted",
    stopped: "Stopped",
    unsupported_stop: "Unsupported stop",
    failed: "Failed",
  };
  return map[status] ?? String(status);
}

export const TERMINAL_DETECTION_STATUSES = [
  "completed",
  "exhausted",
  "stopped",
  "unsupported_stop",
  "failed",
] as const;

export function isTerminalDetection(status: EchoDetectionStatus): boolean {
  return (TERMINAL_DETECTION_STATUSES as readonly string[]).includes(status);
}

/** Continue is offered for finished-but-natural detections (plan §3.2). */
export function canContinue(detection: EchoDetection): boolean {
  return ["completed", "exhausted", "stopped"].includes(
    detection.status,
  );
}

// ---------------------------------------------------------------------------
// On-demand lenses (video | channel) recomputed from stored crawl edges
// ---------------------------------------------------------------------------

export type EchoProjection = "video" | "channel";

export interface EchoLensTopVideo {
  video_id: string;
  title: string | null;
  channel_id: string | null;
  channel_name: string | null;
  in_degree: number;
  out_degree: number;
}

export interface EchoLensTopChannel {
  channel_id: string;
  channel_name: string | null;
  weighted_in_degree: number;
  share: number | null;
}

export interface EchoChannelShare {
  channel_id: string;
  channel_name: string | null;
  weight: number;
  share: number;
}

export interface EchoLensSeed {
  video_id: string;
  title?: string | null;
  thumbnail_url?: string | null;
  channel_id?: string | null;
  channel_name?: string | null;
  url?: string | null;
}

export interface EchoLens {
  detection_id: string;
  projection: EchoProjection;
  seed_run_id: string | null;
  family_run_count: number;
  edge_count: number;
  signals: EchoLayerSignals;
  score: EchoScore;
  top_videos: EchoLensTopVideo[];
  top_channels: EchoLensTopChannel[];
  seed: EchoLensSeed | null;
  computed_at: string;
}

// ---------------------------------------------------------------------------
// Timeline shaping
// ---------------------------------------------------------------------------

export interface EchoTimelineRow {
  layerIndex: number;
  layerRunId: string;
  nodesDiscovered: number;
  edgesObserved: number;
  nodesTotal: number | null;
  collapsePercent: number | null; // S1 cumulative, percent
  topChannelShare: number | null; // S3 top1 share
  communityShare: number | null; // S2 raw community share
  commenterOverlap: number | null; // S5 mean jaccard
  statuses: {
    s1: EchoSignalStatus;
    s2: EchoSignalStatus;
    s3: EchoSignalStatus;
    s4: EchoSignalStatus;
    s5: EchoSignalStatus;
  };
}

function signalValue(signal: EchoSignal | undefined): number | null {
  if (!signal || signal.status !== "available") return null;
  return signal.value ?? null;
}

/** Flatten a detection's append-only snapshots into render-ready rows. */
export function shapeTimeline(layers: EchoLayerSnapshot[]): EchoTimelineRow[] {
  return [...layers]
    .sort((a, b) => a.layer_index - b.layer_index)
    .map((snap) => ({
      layerIndex: snap.layer_index,
      layerRunId: snap.layer_run_id,
      nodesDiscovered: snap.nodes_discovered,
      edgesObserved: snap.edges_observed,
      nodesTotal: snap.nodes_total ?? null,
      collapsePercent: signalValue(snap.signals?.s1),
      topChannelShare: signalValue(snap.signals?.s3),
      communityShare:
        typeof snap.signals?.s2?.detail?.community_share === "number"
          ? (snap.signals.s2.detail.community_share as number)
          : null,
      commenterOverlap: signalValue(snap.signals?.s5),
      statuses: {
        s1: snap.signals?.s1?.status ?? "unavailable",
        s2: snap.signals?.s2?.status ?? "unavailable",
        s3: snap.signals?.s3?.status ?? "unavailable",
        s4: snap.signals?.s4?.status ?? "unavailable",
        s5: snap.signals?.s5?.status ?? "unavailable",
      },
    }));
}

// ---------------------------------------------------------------------------
// Structural lenses (spec §35-§38): /structure + /audience payloads
// ---------------------------------------------------------------------------

/** §36 metadata envelope shared by every structural metric. */
export interface MetricEnvelope {
  metric: string;
  value: number | null;
  status: EchoSignalStatus;
  category: string;
  lens: string;
  numerator?: number | null;
  denominator?: number | null;
  definition?: string;
  detail?: Record<string, unknown>;
}

export interface NullModelPayload {
  metric: string;
  status: EchoSignalStatus;
  observed?: MetricEnvelope;
  null_mean: number | null;
  null_sd: number | null;
  z_score: number | null;
  empirical_percentile: number | null;
  n_randomizations: number;
  seed: number;
  preserves?: string[];
  does_not_preserve?: string[];
  null_values?: number[];
  detail?: { reason?: string };
}

export interface PersistenceRow {
  layer_index: number;
  node_count: number;
  edge_count: number;
  seed_community_share: number | null;
  dominant_community_share: number | null;
  within_community_recommendation_rate: number | null;
  persistence_jaccard_vs_previous: number | null;
  status: EchoSignalStatus;
  reason?: string;
}

export interface CommunityRow {
  size: number;
  is_seed_community?: boolean;
  members?: string[];
  conductance: MetricEnvelope;
  internal_external_edge_ratio: MetricEnvelope;
}

export interface SeedCommunitySummary {
  contains_seed: boolean;
  size?: number;
  share?: number | null;
  members_sample?: string[];
  conductance?: MetricEnvelope;
  internal_external_edge_ratio?: MetricEnvelope;
  status?: EchoSignalStatus;
  reason?: string;
}

export interface CommunityStructure {
  community_count: MetricEnvelope;
  largest_community_size: MetricEnvelope;
  modularity: MetricEnvelope;
  seed_community: SeedCommunitySummary | null;
  communities: CommunityRow[];
}

export interface ChannelConcentration {
  top_channel_share: MetricEnvelope;
  hhi: MetricEnvelope;
  unique_channel_count: MetricEnvelope;
  shares: { channel_id: string; weight: number; share: number }[];
}

export interface EchoStructure {
  detection_id: string;
  seed_run_id: string | null;
  family_run_count: number;
  computed_at: string;
  disclaimers: string[];
  video_lens: {
    lens: string;
    network_statistics: MetricEnvelope[];
    community_structure: CommunityStructure;
    reinforcement: {
      within_community_recommendation_rate: MetricEnvelope;
      null_model: NullModelPayload;
      community_persistence: PersistenceRow[];
    };
    centrality: Record<"pagerank" | "hits_hubs" | "hits_authorities", MetricEnvelope>;
  };
  channel_lens: {
    lens: string;
    projection_rule: string;
    network: MetricEnvelope[];
    unattributed_edges: MetricEnvelope;
    concentration: ChannelConcentration;
    weighted_activity_total: MetricEnvelope;
  };
}

export interface AudienceOverlapBlock {
  jaccard_mean: MetricEnvelope;
  within_community_jaccard_mean: MetricEnvelope;
  between_community_jaccard_mean: MetricEnvelope;
  videos_with_commenters: MetricEnvelope;
  status: EchoSignalStatus;
  reason?: string;
  pair_count?: number;
}

export interface EchoAudience {
  detection_id: string;
  computed_at: string;
  disclaimers: string[];
  commenter_overlap: AudienceOverlapBlock;
}

/** Verbatim research disclaimers (spec §38) - rendered in the UI footer. */
export const ECHO_DISCLAIMERS: string[] = [
  "The recommendation graph represents observed recommendation relationships between videos. These relationships do not directly represent viewer beliefs, social relationships, ideological agreement, or causation.",
  "Standard network metrics describe structural properties of the observed recommendation graph. They should not be interpreted individually as proof of an Echo Chamber.",
  "The Custom Lens Score is a researcher-defined index combining selected structural signals. Its weights are methodological choices made for this project and are not adopted from a universally validated Echo Chamber index.",
  "A strong structural signal does not by itself establish content homophily, shared beliefs, or psychological effects on viewers.",
];

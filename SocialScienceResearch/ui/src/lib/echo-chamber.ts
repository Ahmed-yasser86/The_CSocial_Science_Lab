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
  weight_effective: number;
  status: EchoSignalStatus;
}

export type EchoVerdict =
  | "no_chamber_yet"
  | "weak"
  | "moderate"
  | "strong"
  | "inconclusive";

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
// Verdict bands (plan §2.2 thresholds)
// ---------------------------------------------------------------------------

export function scoreBand(value: number | null): EchoVerdict | null {
  if (value === null || value === undefined) return null;
  if (value < 0.4) return "no_chamber_yet";
  if (value <= 0.6) return "weak";
  if (value <= 0.75) return "moderate";
  return "strong";
}

/** Tailwind classes per verdict band for the chip in the UI. */
export const VERDICT_CHIP_CLASSES: Record<EchoVerdict, string> = {
  no_chamber_yet: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  weak: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  moderate: "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-300",
  strong: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
  inconclusive: "bg-muted text-muted-foreground",
};

export const VERDICT_LABELS: Record<EchoVerdict, string> = {
  no_chamber_yet: "No chamber yet",
  weak: "Weak structure",
  moderate: "Moderate structure",
  strong: "Strong structure",
  inconclusive: "Inconclusive",
};

export const VERDICT_DESCRIPTIONS: Record<EchoVerdict, string> = {
  no_chamber_yet:
    "After the crawled layers, the observed structure does not look like an echo chamber yet.",
  weak:
    "Some observed signals lean toward repeated, concentrated recommendations.",
  moderate:
    "A substantial share of crawled edges returned to already-crawled content.",
  strong:
    "Most new edges returned to already-crawled content and the network is highly concentrated.",
  inconclusive:
    "Not all core signals could be observed, so no verdict is claimed. The indicative score is shown for transparency only.",
};

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

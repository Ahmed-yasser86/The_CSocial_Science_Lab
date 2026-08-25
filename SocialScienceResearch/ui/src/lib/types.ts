export interface Paginated<T> {
  items: T[];
  next_cursor: string | null;
  has_more: boolean;
  total: number;
}

export type Availability = "available" | "missing" | "unsupported";

export type RunType = "channel" | "video" | "recommendation" | "layer";

export type CollectionStatus = "pending" | "running" | "success" | "partial" | "failed";

export interface ValueWithAvailability {
  value: number | null;
  availability: Availability;
}

export interface CollectionError {
  error_id: string;
  run_id: string;
  entity_type: string;
  entity_id: string | null;
  error_type: string;
  message: string;
  occurred_at: string;
  retryable: boolean;
  details: Record<string, unknown>;
}

export interface CollectionResult {
  run_id: string;
  run_type: RunType;
  status: CollectionStatus;
  target_url: string;
  target_id: string | null;
  entities_discovered: number;
  entities_created: number;
  entities_existing: number;
  entities_failed: number;
  comments_collected: number;
  errors: CollectionError[];
  started_at: string | null;
  finished_at: string | null;
}

export interface CollectionRun {
  run_id: string;
  run_type: RunType;
  target_url: string;
  target_channel_id: string | null;
  target_video_id: string | null;
  started_at: string;
  finished_at: string | null;
  status: CollectionStatus;
  provider: string;
  provider_version: string | null;
  config_json: Record<string, unknown>;
  entities_discovered: number;
  entities_succeeded: number;
  entities_existing: number;
  entities_failed: number;
  comments_collected: number;
  notes: string[];
  name?: string | null;
}

export interface ChannelOverview {
  channel_id: string;
  subscriber_count: ValueWithAvailability;
  video_count: ValueWithAvailability;
  view_count: ValueWithAvailability;
  observed_at: string | null;
}

export interface Video {
  video_id: string;
  url: string;
  channel_id: string | null;
  title: string | null;
  description: string | null;
  duration: number | null;
  upload_date: string | null;
  upload_timestamp: string | null;
  tags: string[];
  categories: string[];
  language: string | null;
  live_status: string | null;
  availability: string | null;
  age_limit: number | null;
  is_short: boolean | null;
  thumbnail_url: string | null;
  chapters_json: Record<string, unknown>[];
  transcript_path: string | null;
  transcript_status: string | null;
  transcript_lang: string | null;
  first_observed_run_id: string;
  raw_json: Record<string, unknown>;
  comment_count?: number | null;
}

export type TranscriptStatus = "available" | "missing" | "unsupported";

export interface VideoObservation {
  observation_id: string;
  collection_run_id: string;
  video_id: string;
  observed_at: string;
  view_count: number | null;
  like_count: number | null;
  comment_count: number | null;
  raw_json?: Record<string, unknown>;
}

export type CollectionTargetKind = "channel" | "video" | "recommendation";

export interface CollectionTarget {
  kind: CollectionTargetKind;
  url: string;
}

export interface CollectionSpec {
  targets: CollectionTarget[];
  collect_comments?: boolean | null;
  scrape_all_comments?: boolean | null;
  max_comments_per_video?: number | null;
  comment_min_likes?: number | null;
  comment_date_from?: string | null;
  comment_date_to?: string | null;
  collect_transcripts?: boolean | null;
  enrich_video_stats?: boolean | null;
  max_videos_to_enrich?: number | null;
  max_videos_per_channel?: number | null;
  sampling_seed?: number | null;
  video_criteria?: QueryGroup | null;
  comment_criteria?: QueryGroup | null;
  include_live_videos?: boolean | null;
  video_tabs?: string[] | null;
  scrape_live_only?: boolean | null;
}

export type JobStatus =
  | "pending"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";

export interface JobProgress {
  stage: string;
  discovered: number;
  succeeded: number;
  failed: number;
  message: string | null;
  /** Honest completion percentage over known units; null when unknown. */
  percent_complete?: number | null;
  /** Rolling estimate from completed items; null until observable. */
  eta_seconds?: number | null;
  /** True only when eta_seconds is a real estimate. */
  eta_available?: boolean;
  edges_saved?: number | null;
  current_target?: {
    video_id: string;
    title?: string | null;
    url?: string | null;
  } | null;
  failures?: { video_id: string; error: string }[] | null;
}

export interface Job {
  job_id: string;
  kind: string;
  status: JobStatus;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  progress: JobProgress;
  message: string | null;
  cancel_requested: boolean;
}

export interface CollectJobResult {
  target_count: number;
  results: CollectionResult[];
}

export interface CoverageReport {
  generated_at: string;
  total_channels: number;
  total_videos: number;
  total_comments: number;
  videos_with_comments: number;
  comment_coverage: number;
  transcripts_available: number;
  transcripts_missing: number;
  transcripts_unsupported: number;
  transcript_coverage: number;
  total_runs: number;
  last_run_id: string | null;
  last_run_at: string | null;
}

export interface DatasetSummary {
  generated_at: string;
  channels: number;
  videos: number;
  comments: number;
  transcripts_available: number;
  transcript_coverage: number;
  runs: number;
}

export interface CommentThread {
  comment: Comment;
  replies: Comment[];
}

export interface TopVideoRow {
  video_id: string;
  title: string | null;
  observed_at: string | null;
  [metric: string]: string | number | null | undefined;
}

export interface TopVideosResult {
  channel_id: string;
  metric: string;
  top: TopVideoRow[];
}

export type SamplingStrategy =
  | "top_views"
  | "bottom_views"
  | "top_likes"
  | "bottom_likes"
  | "top_engagement"
  | "bottom_engagement"
  | "top_comments"
  | "top_replies"
  | "top_comment_rate"
  | "top_like_rate"
  | "longest"
  | "shortest"
  | "random"
  | "stratified"
  | "latest"
  | "earliest"
  | "date_range";

export interface SamplingSpec {
  strategy: SamplingStrategy;
  size?: number | null;
  percent?: number | null;
  seed?: number | null;
  strata?: "year" | "month" | "weekday" | null;
  sample_per_stratum?: number | null;
  date_from?: string | null;
  date_to?: string | null;
  top_n?: number | null;
}

export interface SamplingResult {
  strategy: string;
  entity_type: "video" | "comment";
  population_size: number;
  sample_size: number;
  entity_ids: string[];
  criteria_json: Record<string, unknown>;
  seed: number | null;
  missing_metric_count: number;
}

export interface VideoEngagement {
  video_id: string;
  views: ValueWithAvailability;
  likes: ValueWithAvailability;
  comments: ValueWithAvailability;
  engagement_rate: ValueWithAvailability;
  like_rate: ValueWithAvailability;
  comment_rate: ValueWithAvailability;
  observed_at: string | null;
}

export interface CommentPercentiles {
  video_id: string;
  availability: Availability;
  observed_like_counts: number[];
  bands: Record<string, number | null>;
}

export interface CommentVelocityBucket {
  bucket: string;
  count: number;
}

export interface Comment {
  comment_id: string;
  video_id: string;
  author_name: string | null;
  author_id: string | null;
  comment_text: string | null;
  published_at: string | null;
  is_reply: boolean;
  parent_comment_id: string | null;
  root_comment_id: string | null;
  is_author: boolean | null;
  first_observed_run_id: string;
  // Latest observation stats
  like_count: number | null;
  reply_count: number | null;
  is_removed: boolean | null;
  raw_json: Record<string, unknown>;
}

export interface RecommendationEdge {
  observation_id: string;
  collection_run_id: string;
  source_video_id: string;
  recommended_video_id: string;
  position: number | null;
  status: "observed" | "unsupported" | "failed";
  channel_id: string | null;
  title: string | null;
  run_type: string | null;
  raw_json: Record<string, unknown>;
}

export interface NetworkSummary {
  node_count: number;
  edge_count: number;
  source_count: number;
  target_count: number;
  most_recommended: { video_id: string; times_recommended: number }[];
  most_active_sources: { video_id: string; outgoing: number }[];
  highest_pagerank: { video_id: string; pagerank: number }[];
}

export interface VideoNetworkContext {
  video_id: string;
  in_degree: number;
  out_degree: number;
  pagerank: number | null;
  recommended_by: {
    source_video_id: string;
    position: number | null;
    run_id: string | null;
    title: string | null;
    run_type: string | null;
  }[];
  recommends: {
    recommended_video_id: string;
    position: number | null;
    run_id: string | null;
    title: string | null;
    run_type: string | null;
  }[];
  graph_edges: {
    source_video_id: string;
    recommended_video_id: string;
    position: number | null;
    run_id: string | null;
    title: string | null;
    run_type: string | null;
  }[];
  node_channels: Record<string, string>;
}

export interface VideoFilter {
  date_from?: string;
  date_to?: string;
  video_type?: "short" | "long" | "live";
  duration_min?: number;
  duration_max?: number;
  views_min?: number;
  views_max?: number;
  upload_hour?: number;
  upload_weekday?: number;
  keywords?: string[];
  tags?: string[];
  category?: string;
}

// ---------------------------------------------------------------------------
// Research query (B1 contract)
// ---------------------------------------------------------------------------

export type ResearchEntity = "video" | "comment" | "channel" | "recommendation" | "author";

export type QueryOperator =
  | "eq"
  | "neq"
  | "gt"
  | "gte"
  | "lt"
  | "lte"
  | "contains"
  | "not_contains"
  | "in"
  | "not_in"
  | "between"
  | "is_null"
  | "not_null"
  | "top_pct"
  | "bottom_pct"
  | "percentile_rank"
  | "quartile"
  | "quantile"
  | "median_split";

export type QueryGroupOp = "AND" | "OR" | "NOT";

export type VariableSource = "observed" | "derived" | "raw";

export interface VariableMeta {
  entity: ResearchEntity;
  name: string;
  data_type: string;
  source: VariableSource;
  description: string;
  unit: string | null;
  availability: string;
  limits: string | null;
}

export interface OperatorInfo {
  name: QueryOperator;
  description: string;
}

export interface QueryCondition {
  variable: string;
  operator: QueryOperator;
  value?: unknown | null;
  values?: unknown[] | null;
  quantile_n?: number | null;
  quartile?: number | null;
}

export interface QueryGroup {
  operator: QueryGroupOp;
  conditions: Array<QueryCondition | QueryGroup>;
}

export interface QueryContext {
  channel_id?: string | null;
  video_id?: string | null;
}

export interface ResearchQuery {
  entity: ResearchEntity;
  root: QueryGroup;
  query_context?: QueryContext | null;
}

export interface QueryPreviewStage {
  condition: string;
  matched: number;
  cumulative: number;
}

export interface QueryPreviewResult {
  total: number;
  stages: QueryPreviewStage[];
  population_size: number;
  n: number;
}

export interface QueryResolveResult {
  total: number;
  population_size: number;
}

// ---------------------------------------------------------------------------
// Global search (E2 contract)
// ---------------------------------------------------------------------------

export interface SearchHit {
  entity: ResearchEntity;
  entity_id: string;
  title: string | null;
  subtitle: string | null;
  score: number;
  extra: Record<string, unknown>;
}

export interface SearchResult {
  items: SearchHit[];
  next_cursor: string | null;
  has_more: boolean;
  total: number | null;
}

// ---------------------------------------------------------------------------
// Run videos
// ---------------------------------------------------------------------------

export interface RunVideo extends Video {
  first_observed_run_id: string;
}

// ---------------------------------------------------------------------------
// Comment stats
// ---------------------------------------------------------------------------

export interface CommentStats {
  max_replies: number;
  max_unique_repliers: number;
  total_replies: number;
  total_unique_repliers: number;
}

// ---------------------------------------------------------------------------
// System folders
// ---------------------------------------------------------------------------

export interface SystemFolders {
  workbook_path: string;
  transcripts_dir: string;
  datasets_dir: string;
  samples_dir: string;
  data_dir: string;
}

// ---------------------------------------------------------------------------
// Export
// ---------------------------------------------------------------------------

export interface ExportRequest {
  entity_type?: "video" | "comment" | "channel" | "run" | "sample" | "dataset";
  ids?: string[];
  columns?: string[];
  filename?: string;
  project_id?: string;
}

export interface ExportResponse {
  job_id: string;
  status: "pending" | "running" | "succeeded" | "failed";
  download_url: string | null;
  expires_at: string | null;
}

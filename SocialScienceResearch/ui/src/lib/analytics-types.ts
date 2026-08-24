export type VelocityBucket = "hour" | "day";

/**
 * Shared envelope for derived statistics (Gini, concentration, …). Values are
 * always observed from the collected corpus — never estimated.
 */
export interface StatisticEnvelope {
  metric: string;
  value: number | null;
  n: number;
  population_size: number;
  method: string;
  [key: string]: unknown;
}

export interface AuthorCommentCount {
  author_id?: string | null;
  author_name?: string | null;
  comment_count: number;
  [key: string]: unknown;
}

export interface ParticipationAnalytics {
  video_id: string;
  total_comments: number;
  unique_authors: number;
  repeat_authors: number;
  repeat_author_share?: number | null;
  /** Documented shape: bare number. Some builds return the statistics envelope. */
  participation_gini?: StatisticEnvelope | number | null;
  gini?: StatisticEnvelope | null;
  /** Documented shape: bare number. Some builds return the statistics envelope. */
  top_10pct_concentration?: StatisticEnvelope | number | null;
  author_comment_counts?: AuthorCommentCount[];
  [key: string]: unknown;
}

export interface ThreadSizeBreakdown {
  root_comment_id: string;
  size: number;
  depth: number;
  [key: string]: unknown;
}

export interface ReplyMetrics {
  video_id: string;
  total_comments: number;
  reply_count: number;
  reply_rate?: number | null;
  orphan_reply_count: number;
  thread_count: number;
  deepest_thread_depth: number;
  thread_size_mean?: number | null;
  thread_size_median?: number | null;
  threads?: ThreadSizeBreakdown[];
  [key: string]: unknown;
}

export interface VelocityPoint {
  bucket: string;
  count: number;
  [key: string]: unknown;
}

export interface CommentAge {
  mean_seconds?: number | null;
  median_seconds?: number | null;
  negative_age_count?: number | null;
  [key: string]: unknown;
}

export interface VelocityDecay {
  video_id: string;
  bucket: VelocityBucket | string;
  total_comments?: number;
  timestamped_comments?: number;
  missing_published_at?: number;
  upload_missing?: boolean;
  /** Documented shape. */
  timeline?: VelocityPoint[];
  /** Alternative shape used by some builds. */
  points?: VelocityPoint[];
  first_24h_share?: number | null;
  first_7d_share?: number | null;
  comment_age?: CommentAge | null;
  [key: string]: unknown;
}

export interface ChannelHistoryPoint {
  observation_id: string;
  collection_run_id: string;
  observed_at: string;
  subscriber_count?: number | null;
  video_count?: number | null;
  view_count?: number | null;
  subscriber_growth_pct?: number | null;
  video_growth_pct?: number | null;
  view_growth_pct?: number | null;
  [key: string]: unknown;
}

export interface VideoHistoryPoint {
  observation_id: string;
  collection_run_id: string;
  observed_at: string;
  view_count?: number | null;
  like_count?: number | null;
  comment_count?: number | null;
  favorite_count?: number | null;
  view_growth_pct?: number | null;
  like_growth_pct?: number | null;
  comment_growth_pct?: number | null;
  favorite_growth_pct?: number | null;
  [key: string]: unknown;
}

export interface PaginatedHistory<T> {
  items: T[];
  next_cursor?: string | null;
  has_more: boolean;
  total?: number | null;
  [key: string]: unknown;
}

export interface RunDeltaMetric {
  metric: string;
  absolute_change?: number | null;
  change_pct?: number | null;
  a?: number | null;
  b?: number | null;
  [key: string]: unknown;
}

export interface RunDeltaReport {
  from_run?: string;
  to_run?: string;
  run_id_a?: string;
  run_id_b?: string;
  metrics?: RunDeltaMetric[];
  new_entities?: unknown[];
  disappeared_entities?: unknown[];
  [key: string]: unknown;
}
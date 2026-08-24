export type SampleEntityType = "video" | "comment" | "channel" | "recommendation";

export interface SamplingStrategyOption {
  value: string;
  label: string;
  description: string;
  entityType: "video" | "comment" | "both";
}

export const SAMPLING_STRATEGIES: SamplingStrategyOption[] = [
  { value: "top_views", label: "Top by views", description: "Highest view counts first.", entityType: "video" },
  { value: "bottom_views", label: "Bottom by views", description: "Lowest view counts first.", entityType: "video" },
  { value: "top_likes", label: "Top by likes", description: "Highest like counts first.", entityType: "both" },
  { value: "bottom_likes", label: "Bottom by likes", description: "Lowest like counts first.", entityType: "video" },
  { value: "top_engagement", label: "Top by engagement rate", description: "Highest (likes+comments)/views.", entityType: "video" },
  { value: "bottom_engagement", label: "Bottom by engagement rate", description: "Lowest (likes+comments)/views.", entityType: "video" },
  { value: "top_comments", label: "Top by comments", description: "Highest comment counts first.", entityType: "video" },
  { value: "top_comment_rate", label: "Top by comment rate", description: "Highest comments/views.", entityType: "video" },
  { value: "top_like_rate", label: "Top by like rate", description: "Highest likes/views.", entityType: "video" },
  { value: "longest", label: "Longest", description: "Longest duration first.", entityType: "video" },
  { value: "shortest", label: "Shortest", description: "Shortest duration first.", entityType: "video" },
  { value: "latest", label: "Latest published", description: "Most recent first.", entityType: "both" },
  { value: "earliest", label: "Earliest published", description: "Oldest first.", entityType: "both" },
  { value: "date_range", label: "Date range", description: "Published within the chosen window.", entityType: "both" },
  { value: "random", label: "Random (seeded)", description: "Seeded random order for reproducibility.", entityType: "both" },
  { value: "stratified", label: "Stratified", description: "Balanced per year/month/weekday stratum.", entityType: "both" },
];

export interface AdvancedSamplingSpec {
  // Sampling strategy
  strategy: string;
  size?: number;
  percent?: number;
  seed?: number;
  strata?: "year" | "month" | "weekday";
  sample_per_stratum?: number;
  date_from?: string;
  date_to?: string;
  top_n?: number;

  // Scope filters
  entity_type: "video" | "comment";
  channel_ids?: string[];
  video_ids?: string[];
  author_ids?: string[];
  exclude_author_ids?: string[];
  include_all_channels?: boolean;

  // Video-level filters
  video_type?: string;
  duration_min?: number;
  duration_max?: number;
  views_min?: number;
  views_max?: number;
  upload_hour?: number;
  upload_weekday?: number;
  keywords?: string[];
  tags?: string[];
  category?: string;

  // Comment-level filters
  min_likes?: number;
  max_likes?: number;
  min_replies?: number;
  max_replies?: number;
  only_roots?: boolean;
  only_replies?: boolean;
  is_author?: boolean;
  comment_keywords?: string[];
}

export interface Sample {
  sample_id: string;
  entity_type: SampleEntityType;
  strategy: string;
  population_query_hash: string;
  population_size: number;
  sample_size: number;
  seed: number | null;
  criteria_json: Record<string, unknown>;
  member_ids: string[];
  overflow: boolean;
  created_at: string;
  created_by_run_id: string | null;
}

export interface CreateSampleInput {
  entity_type: SampleEntityType;
  strategy: string;
  seed?: number | null;
  criteria_json?: Record<string, unknown>;
  population_size: number;
  population_query_hash?: string;
  member_ids: string[];
  created_by_run_id?: string | null;
}

export interface PairwiseOverlap {
  intersection_size: number;
  union_size: number;
  jaccard: number;
}

export interface SampleCompareResult {
  sample_ids: string[];
  counts: Record<string, number>;
  union_size: number;
  intersection_size: number;
  pairwise: Record<string, PairwiseOverlap>;
  criteria_diffs: Record<string, string[]>;
  metrics: string[];
}

export interface DeleteSampleResult {
  sample_id: string;
  deleted: boolean;
}

export interface Paginated<T> {
  items: T[];
  next_cursor: string | null;
  has_more: boolean;
  total: number;
}

export const SAMPLE_ENTITY_OPTIONS: { value: SampleEntityType; label: string }[] = [
  { value: "video", label: "Video" },
  { value: "comment", label: "Comment" },
  { value: "channel", label: "Channel" },
  { value: "recommendation", label: "Recommendation" },
];

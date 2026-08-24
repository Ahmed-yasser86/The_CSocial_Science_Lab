export type Normalization = "none" | "per_1k" | "z_score";

export type ComparisonMode = "videos" | "channels" | "periods" | "cohorts" | "runs";

export interface ComparisonMetricRow {
  entity_id: string;
  title?: string | null;
  metric: string;
  value?: number | null;
  normalized?: number | null;
  percentile_rank?: number | null;
  is_outlier?: boolean;
  availability?: string;
  observed_at?: string | null;
}

export interface OutlierSummary {
  metric: string;
  method?: string;
  threshold?: number;
  outlier_count?: number;
  outlier_values?: number[];
  n?: number;
  population_size?: number;
}

export interface EntityComparison {
  entity_type: string;
  entity_ids: string[];
  metrics: string[];
  normalization: string;
  population_size: number;
  n: number;
  method: string;
  rows: ComparisonMetricRow[];
  outliers: OutlierSummary[];
}

export interface MetricStat {
  metric: string;
  mean?: number | null;
  median?: number | null;
  n?: number;
  population_size?: number;
  method?: string;
}

export interface PeriodSummary {
  name: string;
  start: string;
  end: string;
  entity_count: number;
  n: number;
  metrics: MetricStat[];
}

export interface PeriodChange {
  metric: string;
  growth_percent?: number | null;
  method?: string;
  n?: number;
}

export interface PeriodComparison {
  entity: string;
  period_a: PeriodSummary;
  period_b: PeriodSummary;
  changes: PeriodChange[];
  population_size: number;
  n: number;
  method: string;
}

export interface CohortSummary {
  name: string;
  count: number;
  n: number;
  metrics: MetricStat[];
}

export interface CohortChange {
  from_cohort: string;
  to_cohort: string;
  metric: string;
  growth_percent?: number | null;
  method?: string;
}

export interface CohortComparison {
  cohorts: CohortSummary[];
  changes: CohortChange[];
  population_size: number;
  n: number;
  method: string;
}

export interface RunSnapshot {
  run_id: string;
  started_at?: string | null;
  entity_counts: Record<string, number>;
  metrics: Record<string, number | null>;
  n?: number;
  population_size?: number;
  method?: string;
}

export interface RunTransition {
  from_run: string;
  to_run: string;
  entity_type?: string;
  new_entities: string[];
  disappeared_entities: string[];
}

export interface RunComparison {
  run_ids: string[];
  metrics: string[];
  snapshots: RunSnapshot[];
  transitions: RunTransition[];
  population_size: number;
  n: number;
  method: string;
}

export interface PeriodBodyInput {
  name?: string | null;
  start: string;
  end: string;
}

export interface CompareVideosInput {
  video_ids: string[];
  metrics: string[];
  normalization?: Normalization;
}

export interface CompareChannelsInput {
  channel_ids: string[];
  metrics: string[];
  normalization?: Normalization;
}

export interface ComparePeriodsInput {
  period_a: PeriodBodyInput;
  period_b: PeriodBodyInput;
  entity?: "video" | "channel";
  metrics: string[];
}

export interface CompareCohortsInput {
  cohorts: { name: string; channel_id?: string | null }[];
  metrics: string[];
}

export interface CompareRunsInput {
  run_ids: string[];
  metrics: string[];
}

export const ENTITY_METRICS: Record<"video" | "channel", string[]> = {
  video: ["views", "likes", "comments", "favorites"],
  channel: ["subscribers", "videos", "views"],
};

export const NORMALIZATION_LABEL: Record<Normalization, string> = {
  none: "Raw values",
  per_1k: "Per 1,000 subscribers",
  z_score: "Z-score (within set)",
};

import type { ResearchEntity } from "@/lib/types";

export type ExplorerEntity = ResearchEntity;

export type ExplorerOperator =
  | "eq"
  | "neq"
  | "contains"
  | "not_contains"
  | "in"
  | "not_in"
  | "gt"
  | "gte"
  | "lt"
  | "lte"
  | "is_null"
  | "not_null";

export interface ExplorerFilter {
  variable: string;
  operator: ExplorerOperator;
  value?: unknown;
}

export interface ExplorerSortOption {
  variable: string;
  data_type: string;
}

export interface ExplorerColumn {
  entity: ExplorerEntity;
  name: string;
  data_type: string;
  source: string;
  description: string;
  unit: string | null;
  availability: string;
  limits: string | null;
}

export interface ExplorePage {
  entity: ExplorerEntity;
  columns: ExplorerColumn[];
  items: Record<string, unknown>[];
  next_cursor: string | null;
  has_more: boolean;
  total: number | null;
  sort_options: ExplorerSortOption[];
}

export interface RawRecord {
  entity: string;
  entity_id: string;
  raw_json: Record<string, unknown>;
}

export interface RunSummary {
  run_id: string;
  run_type?: string | null;
  provider?: string | null;
  provider_version?: string | null;
  config_json?: Record<string, unknown>;
  status?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface ObservationPoint {
  observed_at?: string | null;
  run_id?: string | null;
}

export interface ProvenanceRecord {
  entity: string;
  entity_id: string;
  first_observed_run_id?: string | null;
  first_seen_at?: string | null;
  runs?: RunSummary[];
  observation_count?: number;
  observations?: ObservationPoint[];
  provider?: string | null;
  config_json?: Record<string, unknown>;
  channel_id?: string | null;
  parent_comment_id?: string | null;
  root_comment_id?: string | null;
}

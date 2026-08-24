import type { QueryGroup, ResearchEntity } from "@/lib/types";

export type DatasetEntityType = ResearchEntity;

export { type Paginated } from "@/lib/types";

export interface CreateDatasetInput {
  name: string;
  description?: string;
  entity_type: DatasetEntityType;
  project_id?: string;
  include_raw?: boolean;
  run_ids?: string[];
  channel_ids?: string[];
  video_ids?: string[];
  member_ids?: string[];
  criteria?: QueryGroup | null;
  variable_selection?: string[];
}

export interface Dataset {
  dataset_id: string;
  name: string;
  description: string | null;
  entity_type: DatasetEntityType;
  project_id: string | null;
  include_raw: boolean;
  member_count: number;
  overflow: boolean;
  created_at: string;
  updated_at: string;
}

export interface DatasetQuality {
  dataset_id: string;
  completeness: number;
  validity: number;
  consistency: number;
  timeliness: number;
  overall_coverage: number;
  generated_at: string;
  columns: QualityColumn[];
  checks: QualityCheck[];
}

export interface QualityColumn {
  name: string;
  type: string;
  completeness: number;
  validity: number;
  distinct_count: number;
  null_count: number;
  present: number;
  missing: number;
  missing_share: number;
}

export interface QualityCheck {
  name: string;
  status: "pass" | "warn" | "fail";
  message: string;
  affected_count: number;
}

export type DatasetExportFormat = "csv" | "json";

export interface DatasetDeleteResult {
  dataset_id: string;
  deleted: boolean;
}

export interface ResearchProject {
  project_id: string;
  name: string;
  description: string | null;
  notes: string | null;
  targets: ProjectTarget[];
  variable_selection: string[];
  created_at: string;
  updated_at: string;
  config_hash: string;
}

export interface ProjectTarget {
  kind: ProjectTargetKind;
  url: string;
}

export type ProjectTargetKind = "channel" | "video" | "recommendation";

export interface CreateProjectInput {
  name: string;
  description?: string;
  notes?: string;
  targets: ProjectTarget[];
  variable_selection: string[];
}

export interface UpdateProjectInput {
  name?: string;
  description?: string;
  notes?: string;
  targets?: ProjectTarget[];
  variable_selection?: string[];
}

export interface ProjectDeleteResult {
  project_id: string;
  deleted: boolean;
}

export interface Channel {
  channel_id: string;
  title: string | null;
}

export interface SampleLabels {
  system?: Record<string, string>;
  research?: Record<string, string>;
  custom?: Record<string, string>;
}

export interface CombineDatasetsInput {
  name: string;
  description?: string;
  sample_ids: string[];
  deduplicate?: boolean;
  preserve_lineage?: boolean;
  labels?: SampleLabels;
}

export interface Dataset {
  dataset_id: string;
  name: string;
  description: string | null;
  entity_type: DatasetEntityType;
  project_id: string | null;
  include_raw: boolean;
  member_count: number;
  overflow: boolean;
  created_at: string;
  updated_at: string;
  labels?: SampleLabels;
  source_samples?: string[];
}

export interface Project {
  project_id: string;
  name: string;
  description: string | null;
  notes: string | null;
  targets: ProjectTarget[];
  variable_selection: string[];
  created_at: string;
  updated_at: string;
  config_hash: string;
  dataset_ids?: string[];
}

export type ProjectItemType = "sample_group" | "dataset_group" | "mixed";

export interface ProjectItem {
  item_id: string;
  project_id: string;
  name: string;
  description: string | null;
  item_type: ProjectItemType;
  sample_ids: string[];
  dataset_ids: string[];
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface CreateProjectItemInput {
  name: string;
  description?: string;
  item_type?: ProjectItemType;
  sample_ids?: string[];
  dataset_ids?: string[];
  tags?: string[];
}

export interface UpdateProjectItemInput {
  name?: string;
  description?: string;
  item_type?: ProjectItemType;
  sample_ids?: string[];
  dataset_ids?: string[];
  tags?: string[];
}

export interface ProjectItemDeleteResult {
  item_id: string;
  deleted: boolean;
}
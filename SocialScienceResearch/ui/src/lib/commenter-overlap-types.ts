/** TS mirrors of the commenter-overlap service models (doc §D4). */

export type IdentityKind = "id" | "name";

export type OverlapMetric = "jaccard" | "overlap_coefficient" | "intersection";

export interface OverlapEntity {
  entity_id: string;
  entity_type: "video" | "channel";
  title?: string | null;
  channel_id?: string | null;
  channel_name?: string | null;
  commenter_count: number;
  comment_count: number;
  identity_coverage?: number | null;
  avg_jaccard?: number | null;
}

export interface SharedCommenter {
  author_key: string;
  author_name?: string | null;
  identity_kind: IdentityKind;
  count_a: number;
  count_b: number;
  total_comments: number;
  first_seen_at?: string | null;
  last_seen_at?: string | null;
}

export interface PairOverlap {
  entity_a: string;
  entity_b: string;
  set_size_a: number;
  set_size_b: number;
  intersection_size: number;
  union_size: number;
  unique_a: number;
  unique_b: number;
  jaccard?: number | null;
  overlap_coefficient?: number | null;
  reach_overlap_pct?: number | null;
  shared_commenters: SharedCommenter[];
  total_shared: number;
}

export interface BridgeCommenter {
  author_key: string;
  author_name?: string | null;
  identity_kind: IdentityKind;
  entity_count: number;
  comment_count: number;
  video_count: number;
  channel_count: number;
  entities: { entity_id: string; comment_count: number }[];
  first_seen_at?: string | null;
  last_seen_at?: string | null;
}

export interface TopSharedCommenter {
  author_key: string;
  author_name?: string | null;
  identity_kind: IdentityKind;
  entity_count: number;
  comment_count: number;
  video_count: number;
  channel_count: number;
}

export interface ProjectionSummary {
  entity_type: "video" | "channel";
  entity_count: number;
  commenter_count: number;
  comment_count: number;
  unidentified_comments: number;
  pair_count: number;
  average_jaccard?: number | null;
  max_jaccard_pair?: {
    entity_a: string;
    entity_b: string;
    jaccard?: number | null;
    intersection_size: number;
  } | null;
  max_shared_pair?: {
    entity_a: string;
    entity_b: string;
    intersection_size: number;
  } | null;
  bridge_commenter_count: number;
}

export interface OverlapEdge {
  entity_a: string;
  entity_b: string;
  shared_commenter_count: number;
  jaccard?: number | null;
}

export interface CommenterProjection {
  entity_type: "video" | "channel";
  entities: OverlapEntity[];
  pairs: PairOverlap[];
  heatmap: Record<string, Record<string, number | null>>;
  overlap_edges: OverlapEdge[];
  bridge_commenters: BridgeCommenter[];
  top_shared_commenters: TopSharedCommenter[];
  summary: ProjectionSummary;
}

export interface CommenterOverlapResult {
  scope: { video_ids: string[]; channel_ids: string[] };
  metric: OverlapMetric;
  videos?: CommenterProjection | null;
  channels?: CommenterProjection | null;
  global_summary: {
    unique_commenters: number;
    comment_count: number;
    bridge_commenter_count: number;
  };
}

export interface ProfileVideoRow {
  video_id: string;
  channel_id?: string | null;
  channel_name?: string | null;
  title?: string | null;
  comment_count: number;
  root_count: number;
  reply_count: number;
  reply_to_count: number;
  first_seen_at?: string | null;
  last_seen_at?: string | null;
}

export interface ProfileChannelRow {
  channel_id: string;
  channel_name?: string | null;
  comment_count: number;
  video_count: number;
  root_count: number;
  reply_count: number;
  first_seen_at?: string | null;
  last_seen_at?: string | null;
}

export interface ProfileComment {
  comment_id: string;
  video_id: string;
  comment_text?: string | null;
  published_at?: string | null;
  is_reply: boolean;
  parent_comment_id?: string | null;
  parent_author_name?: string | null;
  like_count?: number | null;
  is_author?: boolean | null;
}

export interface CommenterProfile {
  author_key: string;
  author_name?: string | null;
  identity_kind: IdentityKind;
  total_comments: number;
  video_count: number;
  channel_count: number;
  is_author?: boolean | null;
  first_seen_at?: string | null;
  last_seen_at?: string | null;
  videos: ProfileVideoRow[];
  channels: ProfileChannelRow[];
  comments: ProfileComment[];
}

import type {
  Comment,
  Video,
  VideoFilter,
  SamplingResult,
  VideoEngagement,
  CommentPercentiles,
  CommentVelocityBucket,
  RecommendationEdge,
  NetworkSummary,
  VideoNetworkContext,
  SearchResult,
  VariableMeta,
  OperatorInfo,
  ResearchQuery,
  QueryPreviewResult,
  QueryResolveResult,
  RunVideo,
  CommentStats,
  SystemFolders,
  ExportRequest,
  Paginated,
  CollectionResult,
  CollectionRun,
  ChannelOverview,
  TopVideosResult,
  VideoObservation,
  Job,
  CollectJobResult,
  CoverageReport,
  DatasetSummary,
  CommentThread,
  CollectionError,
  CollectionSpec,
  RunType,
  SamplingSpec,
} from "@/lib/types";

export type { SamplingResult, SamplingSpec };

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "/api/v1/social-science";

export interface CommentTreeNode {
  comment: Comment;
  replies: CommentTreeNode[];
  total_replies: number;
  max_depth: number;
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: init?.body
      ? { "Content-Type": "application/json", ...init.headers }
      : init?.headers,
    ...init,
  });
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      const detail =
        body?.detail &&
        (typeof body.detail === "string"
          ? body.detail
          : JSON.stringify(body.detail));
      if (body?.message || detail) {
        message = String(body?.message || detail);
      }
    } catch {
      // non-JSON error body
    }
    throw new ApiError(res.status, message);
  }
  return (await res.json()) as T;
}

export function toQuery(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.append(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

function filterToQuery(filter: VideoFilter | undefined): string {
  const params: Record<string, string | number | undefined> = {};
  if (filter?.date_from) params.date_from = filter.date_from;
  if (filter?.date_to) params.date_to = filter.date_to;
  if (filter?.video_type) params.video_type = filter.video_type;
  if (filter?.duration_min !== undefined && filter?.duration_min !== null)
    params.duration_min = filter.duration_min;
  if (filter?.duration_max !== undefined && filter?.duration_max !== null)
    params.duration_max = filter.duration_max;
  if (filter?.views_min !== undefined && filter?.views_min !== null)
    params.views_min = filter.views_min;
  if (filter?.views_max !== undefined && filter?.views_max !== null)
    params.views_max = filter.views_max;
  if (filter?.upload_hour !== undefined && filter?.upload_hour !== null)
    params.upload_hour = filter.upload_hour;
  if (filter?.upload_weekday !== undefined && filter?.upload_weekday !== null)
    params.upload_weekday = filter.upload_weekday;
  if (filter?.category) params.category = filter.category;

  const parts: string[] = [];
  for (const [key, value] of Object.entries(params)) {
    parts.push(`${key}=${encodeURIComponent(String(value))}`);
  }
  for (const keyword of filter?.keywords ?? []) {
    parts.push(`keywords=${encodeURIComponent(keyword)}`);
  }
  for (const tag of filter?.tags ?? []) {
    parts.push(`tags=${encodeURIComponent(tag)}`);
  }
  return parts.length ? `?${parts.join("&")}` : "";
}

// ---------------------------------------------------------------------------
// Collection
// ---------------------------------------------------------------------------
export function collectChannel(url: string): Promise<CollectionResult> {
  return request("/collect/channel", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export function collectVideo(url: string): Promise<CollectionResult> {
  return request("/collect/video", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export function collectRecommendations(url: string): Promise<CollectionResult> {
  return request("/collect/recommendations", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export function submitCollect(spec: CollectionSpec): Promise<{ job_id: string }> {
  return request("/collect", {
    method: "POST",
    body: JSON.stringify(spec),
  });
}

export function getJobs(): Promise<Job[]> {
  return request<Paginated<Job>>("/jobs").then((page) => page.items ?? []);
}

export function getJob(jobId: string): Promise<Job> {
  return request(`/jobs/${jobId}`);
}

export function cancelJob(jobId: string): Promise<{ job_id: string; cancelled: boolean }> {
  return request(`/jobs/${jobId}/cancel`, { method: "POST" });
}

export function getJobResult(jobId: string): Promise<CollectJobResult> {
  return request(`/jobs/${jobId}/result`);
}

// ---------------------------------------------------------------------------
// Quality / coverage
// ---------------------------------------------------------------------------
export function getCoverage(): Promise<CoverageReport> {
  return request("/coverage");
}

export function getDatasetSummary(): Promise<DatasetSummary> {
  return request("/dataset/summary");
}

// ---------------------------------------------------------------------------
// Corpus extras
// ---------------------------------------------------------------------------
export function getVideoObservations(videoId: string): Promise<VideoObservation[]> {
  return request<Paginated<VideoObservation>>(`/videos/${videoId}/observations`).then(
    (page) => page.items ?? [],
  );
}

export function getVideoRaw(
  videoId: string,
): Promise<{ video_id: string; raw_json: Record<string, unknown> }> {
  return request(`/videos/${videoId}/raw`);
}

export function getCommentThreads(videoId: string): Promise<{
  video_id: string;
  threads: CommentThread[];
}> {
  return request(`/videos/${videoId}/comments/threads`);
}

export function getChannelTopVideos(
  channelId: string,
  metric = "views",
  n = 10,
): Promise<TopVideosResult> {
  return request(
    `/channels/${channelId}/videos/top${toQuery({ metric, n })}`,
  );
}

// ---------------------------------------------------------------------------
// Runs (provenance)
// ---------------------------------------------------------------------------
export function getRuns(runType?: RunType): Promise<CollectionRun[]> {
  return request< Paginated<CollectionRun>>(
    `/runs${toQuery({ run_type: runType })}`,
  ).then((page) => page.items ?? []);
}

export function getRun(runId: string): Promise<CollectionRun> {
  return request(`/runs/${runId}`);
}

export function updateRunName(
  runId: string,
  name: string,
): Promise<CollectionRun> {
  return request(`/runs/${runId}`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
}

export function getRunErrors(runId: string): Promise<CollectionError[]> {
  return request(`/runs/${runId}/errors`);
}

export function getRunSubRuns(runId: string): Promise<Paginated<CollectionRun>> {
  return request(`/runs/${runId}/sub-runs`);
}

// ---------------------------------------------------------------------------
// Channels
// ---------------------------------------------------------------------------
export function getChannels(cursor?: string): Promise<Paginated<Channel>> {
  return request(`/channels${toQuery({ cursor })}`);
}

export interface Channel {
  channel_id: string;
  title: string | null;
  url?: string;
  handle?: string | null;
  description?: string | null;
}

// ---------------------------------------------------------------------------
// Corpus / channel
// ---------------------------------------------------------------------------
export function getChannelOverview(channelId: string): Promise<ChannelOverview> {
  return request(`/channels/${channelId}/overview`);
}

export function getChannelVideos(
  channelId: string,
  filter?: VideoFilter,
): Promise<Video[]> {
  return request<Paginated<Video>>(
    `/channels/${channelId}/videos${filterToQuery(filter)}`,
  ).then((page) => page.items ?? []);
}

export function getChannelVideoCount(channelId: string): Promise<{
  channel_id: string;
  count: number;
}> {
  return request(`/channels/${channelId}/videos/count`);
}

export function getVideo(videoId: string): Promise<Video> {
  return request(`/videos/${videoId}`);
}

// ---------------------------------------------------------------------------
// Sampling
// ---------------------------------------------------------------------------
export function sampleVideos(
  channelId: string,
  spec: SamplingSpec,
): Promise<SamplingResult> {
  return request(`/channels/${channelId}/videos/sample`, {
    method: "POST",
    body: JSON.stringify(spec),
  });
}

export function sampleComments(
  videoId: string,
  spec: SamplingSpec,
): Promise<SamplingResult> {
  return request(`/videos/${videoId}/comments/sample`, {
    method: "POST",
    body: JSON.stringify(spec),
  });
}

// ---------------------------------------------------------------------------
// Video analytics
// ---------------------------------------------------------------------------
export function getVideoEngagement(videoId: string): Promise<VideoEngagement> {
  return request(`/videos/${videoId}/engagement`);
}

// ---------------------------------------------------------------------------
// Legacy / network/video endpoint removed - video navigation uses Next.js
// page routes (/network/videos/[videoId]) instead of API calls
// ---------------------------------------------------------------------------

export function getCommentPercentiles(videoId: string): Promise<CommentPercentiles> {
  return request(`/videos/${videoId}/comments/percentiles`);
}

export function getCommentVelocity(
  videoId: string,
  bucket: "day" | "hour" = "day",
): Promise<CommentVelocityBucket[]> {
  return request(`/videos/${videoId}/comments/velocity${toQuery({ bucket })}`);
}

export function getVideoComments(videoId: string): Promise<Comment[]> {
  return request<Paginated<Comment>>(`/videos/${videoId}/comments`).then(
    (page) => page.items ?? [],
  );
}

// ---------------------------------------------------------------------------
// Recommendation network
// ---------------------------------------------------------------------------
export function getVideoRecommendations(videoId: string): Promise<RecommendationEdge[]> {
  return request<Paginated<RecommendationEdge>>(
    `/videos/${videoId}/recommendations`,
  ).then((page) => page.items ?? []);
}

export function getVideoNetworkContext(
  videoId: string,
  runIds?: string[],
): Promise<VideoNetworkContext> {
  return request(
    `/network/recommendations/${videoId}${toQuery({
      run_ids: runIds && runIds.length ? runIds.join(",") : undefined,
    })}`,
  );
}

export function getNetworkSummary(
  runId?: string,
  topN = 10,
): Promise<NetworkSummary> {
  return request(
    `/network/metrics${toQuery({ run_id: runId, top_n: topN })}`,
  );
}

// ---------------------------------------------------------------------------
// Global search (E2 contract)
// ---------------------------------------------------------------------------
export function searchGlobal(
  q: string,
  entity?: string,
  cursor?: string,
  pageSize = 50,
): Promise<SearchResult> {
  return request(
    `/search${toQuery({ q, entity, cursor, page_size: pageSize })}`,
  );
}

// ---------------------------------------------------------------------------
// Research query (B1 contract)
// ---------------------------------------------------------------------------
export function getResearchVariables(
  entity?: string,
): Promise<VariableMeta[]> {
  return request(`/research/variables${toQuery({ entity })}`);
}

export function getResearchOperators(): Promise<OperatorInfo[]> {
  return request("/research/operators");
}

export function previewResearchQuery(
  query: ResearchQuery,
): Promise<QueryPreviewResult> {
  return request("/research/query/preview", {
    method: "POST",
    body: JSON.stringify(query),
  });
}

export function resolveResearchQuery(
  query: ResearchQuery,
): Promise<QueryResolveResult> {
  return request("/research/query/resolve", {
    method: "POST",
    body: JSON.stringify(query),
  });
}

// ---------------------------------------------------------------------------
// Run videos
// ---------------------------------------------------------------------------
export function getRunVideos(runId: string): Promise<RunVideo[]> {
  return request<Paginated<RunVideo>>(`/runs/${runId}/videos`).then(
    (page) => page.items ?? [],
  );
}

// ---------------------------------------------------------------------------
// Comment stats
// ---------------------------------------------------------------------------
export function getCommentStats(videoId: string): Promise<CommentStats> {
  return request(`/videos/${videoId}/comments/stats`);
}

// ---------------------------------------------------------------------------
// System folders
// ---------------------------------------------------------------------------
export function getSystemFolders(): Promise<SystemFolders> {
  return request("/system/folders");
}

// ---------------------------------------------------------------------------
// Export
// ---------------------------------------------------------------------------
export function exportData(request: ExportRequest): Promise<Blob> {
  return fetch(`${API_BASE}/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  }).then((res) => {
    if (!res.ok) {
      throw new ApiError(res.status, "Export failed");
    }
    return res.blob();
  });
}

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
  run_ids?: string[];
  video_ids?: string[];
  author_ids?: string[];
  exclude_author_ids?: string[];
  author_names?: string[];
  exclude_author_names?: string[];
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
  categories?: string[];

  // Comment-level filters
  min_likes?: number;
  max_likes?: number;
  min_replies?: number;
  max_replies?: number;
  only_roots?: boolean;
  only_replies?: boolean;
  is_author?: boolean;
  comment_keywords?: string[];

  // Author-overlap filters
  overlap?: "off" | "video" | "channel";
  overlap_min?: number;
  overlap_video_ids?: string[];
  overlap_channel_ids?: string[];
}

export function sampleAdvanced(
  spec: AdvancedSamplingSpec,
): Promise<SamplingResult> {
  return request("/sampling/advanced", {
    method: "POST",
    body: JSON.stringify(spec),
  });
}

// ---------------------------------------------------------------------------
// Comment tree
// ---------------------------------------------------------------------------
export function getCommentTree(
  videoId: string,
  commentId: string,
): Promise<CommentTreeNode> {
  return request(`/videos/${videoId}/comments/${commentId}/tree`);
}

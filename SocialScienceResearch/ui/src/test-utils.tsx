import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "@/components/ui/toast";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { ReactElement, ReactNode } from "react";
import type {
  Comment,
  Video,
  RunVideo,
  VideoEngagement,
  SystemFolders,
  VariableMeta,
} from "@/lib/types";
import type {
  CommentTreeNode,
} from "@/services/api";
import type {
  Dataset,
  Project,
  DatasetQuality,
  QualityColumn,
} from "@/lib/dataset-types";
import type { Sample } from "@/lib/sample-types";

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: Infinity },
      mutations: { retry: false },
    },
  });
}

export function renderWithProviders(
  ui: ReactElement,
  {
    queryClient = makeQueryClient(),
  }: { queryClient?: QueryClient } = {},
) {
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <ToastProvider>{children}</ToastProvider>
        </TooltipProvider>
      </QueryClientProvider>
    );
  }
  return {
    queryClient,
    user: userEvent.setup(),
    ...render(ui, { wrapper: Wrapper }),
  };
}

export function makeComment(overrides: Partial<Comment> = {}): Comment {
  return {
    comment_id: "c1",
    video_id: "v1",
    author_name: "Author One",
    author_id: "a1",
    comment_text: "First comment text",
    published_at: "2024-01-01T10:00:00Z",
    is_reply: false,
    parent_comment_id: null,
    root_comment_id: null,
    is_author: false,
    first_observed_run_id: "run1",
    like_count: 7,
    reply_count: 2,
    is_removed: false,
    raw_json: {},
    ...overrides,
  };
}

export function makeVideo(overrides: Partial<Video> = {}): Video {
  return {
    video_id: "v1",
    url: "https://example.com/watch?v=v1",
    channel_id: "ch1",
    title: "Example Video",
    description: "A description",
    duration: 125,
    upload_date: "2024-01-01",
    upload_timestamp: "2024-01-01T00:00:00Z",
    tags: ["tag-a", "tag-b"],
    categories: ["education"],
    language: "en",
    live_status: null,
    availability: "public",
    age_limit: null,
    is_short: false,
    thumbnail_url: "https://example.com/thumb.jpg",
    chapters_json: [],
    transcript_path: null,
    transcript_status: null,
    transcript_lang: null,
    first_observed_run_id: "run1",
    raw_json: { id: "v1" },
    ...overrides,
  };
}

export function makeRunVideo(overrides: Partial<RunVideo> = {}): RunVideo {
  const video = makeVideo(overrides);
  return video as RunVideo;
}

export function makeCommentTree(
  overrides: Partial<CommentTreeNode> = {},
): CommentTreeNode {
  return {
    comment: makeComment(),
    replies: [],
    total_replies: 0,
    max_depth: 1,
    ...overrides,
  };
}

export function makeEngagement(
  overrides: Partial<VideoEngagement> = {},
): VideoEngagement {
  return {
    video_id: "v1",
    views: { value: 12345, availability: "available" },
    likes: { value: 999, availability: "available" },
    comments: { value: 456, availability: "available" },
    engagement_rate: { value: 0.05, availability: "available" },
    like_rate: { value: 0.03, availability: "available" },
    comment_rate: { value: 0.02, availability: "available" },
    observed_at: "2024-01-02T00:00:00Z",
    ...overrides,
  };
}

export function makeSystemFolders(
  overrides: Partial<SystemFolders> = {},
): SystemFolders {
  return {
    workbook_path: "/data/workbook",
    transcripts_dir: "/data/transcripts",
    datasets_dir: "/data/datasets",
    samples_dir: "/data/samples",
    data_dir: "/data",
    ...overrides,
  };
}

export function makeVariable(overrides: Partial<VariableMeta> = {}): VariableMeta {
  return {
    entity: "video",
    name: "view_count",
    data_type: "int",
    source: "observed",
    description: "Number of views",
    unit: null,
    availability: "available",
    limits: null,
    ...overrides,
  };
}

export function makeDataset(overrides: Partial<Dataset> = {}): Dataset {
  return {
    dataset_id: "ds1",
    name: "Alpha dataset",
    description: "First dataset",
    entity_type: "video",
    project_id: null,
    include_raw: false,
    member_count: 42,
    overflow: false,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

export function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    project_id: "p1",
    name: "2026 study",
    description: "A study",
    notes: null,
    targets: [],
    variable_selection: ["views"],
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    config_hash: "hash",
    ...overrides,
  };
}

export function makeSample(overrides: Partial<Sample> = {}): Sample {
  return {
    sample_id: "s1",
    entity_type: "video",
    strategy: "random",
    population_query_hash: "abc",
    population_size: 1000,
    sample_size: 500,
    seed: 42,
    criteria_json: {},
    member_ids: [],
    overflow: false,
    created_at: "2024-01-01T00:00:00Z",
    created_by_run_id: null,
    ...overrides,
  };
}

export function makeQuality(): DatasetQuality {
  return {
    dataset_id: "ds1",
    completeness: 0.9,
    validity: 0.9,
    consistency: 0.8,
    timeliness: 1,
    overall_coverage: 0.85,
    generated_at: "2024-01-01T00:00:00Z",
    checks: [],
    columns: [
      {
        name: "video_id",
        type: "string",
        completeness: 1,
        validity: 1,
        distinct_count: 42,
        null_count: 0,
        present: 42,
        missing: 0,
        missing_share: 0,
      },
      {
        name: "title",
        type: "string",
        completeness: 0.8,
        validity: 0.8,
        distinct_count: 40,
        null_count: 8,
        present: 34,
        missing: 8,
        missing_share: 0.190476,
      },
    ] as QualityColumn[],
  };
}
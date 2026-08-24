import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders, makeComment, makeVideo } from "@/test-utils";
import {
  CommentsBrowser,
  resolveTreeRootId,
} from "@/components/features/comments-browser";

vi.mock("next/navigation", () => ({
  useSearchParams: vi.fn(),
  useRouter: vi.fn(),
}));

vi.mock("@/services/api", () => ({
  getVideo: vi.fn(),
}));

vi.mock("@/services/queries", () => ({
  useVideoComments: vi.fn(),
  useCommentPercentiles: vi.fn(),
  useCommentVelocity: vi.fn(),
  useSampleComments: vi.fn(),
  useCommentThreads: vi.fn(),
}));

vi.mock("@/components/features/sampling/SamplingWorkbench", () => ({
  SamplingWorkbench: () => <div>Sampling workbench stub</div>,
}));

vi.mock("@/components/features/comment-tree-modal", () => ({
  CommentTreeModal: ({ commentId }: { commentId: string }) => (
    <div>Comment tree modal for {commentId}</div>
  ),
}));

import { useSearchParams, useRouter } from "next/navigation";
import * as api from "@/services/api";
import * as queries from "@/services/queries";
import type { Comment, CommentThread } from "@/lib/types";

const mockSearchParams = vi.mocked(useSearchParams);
const mockRouter = vi.mocked(useRouter);
const mockGetVideo = vi.mocked(api.getVideo);
const mockUseVideoComments = vi.mocked(queries.useVideoComments);
const mockUseCommentPercentiles = vi.mocked(queries.useCommentPercentiles);
const mockUseCommentVelocity = vi.mocked(queries.useCommentVelocity);
const mockUseSampleComments = vi.mocked(queries.useSampleComments);
const mockUseCommentThreads = vi.mocked(queries.useCommentThreads);

function makeQuery(overrides: Record<string, unknown> = {}) {
  return {
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
    ...overrides,
  };
}

interface MockOptions {
  threadId?: string | null;
  comments?: Comment[];
  threads?: CommentThread[];
}

function setupDefaultMocks({
  threadId = null,
  comments = [makeComment()],
  threads = [],
}: MockOptions = {}) {
  mockSearchParams.mockReturnValue({
    get: (key: string) => (key === "thread" ? threadId : null),
  } as unknown as ReturnType<typeof useSearchParams>);
  mockRouter.mockReturnValue({ replace: vi.fn() } as unknown as ReturnType<typeof useRouter>);
  mockGetVideo.mockResolvedValue(makeVideo());
  mockUseVideoComments.mockReturnValue(
    makeQuery({ data: comments }) as unknown as ReturnType<typeof queries.useVideoComments>,
  );
  mockUseCommentPercentiles.mockReturnValue(
    makeQuery() as unknown as ReturnType<typeof queries.useCommentPercentiles>,
  );
  mockUseCommentVelocity.mockReturnValue(
    makeQuery({ data: [] }) as unknown as ReturnType<typeof queries.useCommentVelocity>,
  );
  mockUseSampleComments.mockReturnValue({
    mutate: vi.fn(),
  } as unknown as ReturnType<typeof queries.useSampleComments>);
  mockUseCommentThreads.mockReturnValue(
    makeQuery({ data: threads }) as unknown as ReturnType<typeof queries.useCommentThreads>,
  );
}

describe("resolveTreeRootId", () => {
  it("prefers root_comment_id over comment_id", () => {
    const comment = makeComment({
      comment_id: "c1",
      parent_comment_id: "p1",
      root_comment_id: "r1",
    });
    expect(resolveTreeRootId(comment)).toBe("r1");
  });

  it("falls back to comment_id when root_comment_id is absent", () => {
    const comment = makeComment({
      comment_id: "c1",
      parent_comment_id: "p1",
      root_comment_id: null,
    });
    expect(resolveTreeRootId(comment)).toBe("c1");
  });

  it("never falls back to parent_comment_id", () => {
    const comment = makeComment({
      comment_id: "c1",
      parent_comment_id: "missing-parent",
      root_comment_id: null,
    });
    expect(resolveTreeRootId(comment)).not.toBe("missing-parent");
  });
});

describe("CommentsBrowser", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the sub-tab layout with a summary line and the all-comments table", async () => {
    setupDefaultMocks();
    const { user } = renderWithProviders(<CommentsBrowser videoId="v1" />);

    expect(screen.getByRole("tab", { name: "All Comments" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Analytics" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Sampling" })).toBeInTheDocument();

    expect(
      screen.getByText(/1 comments collected · 1 roots · 0 replies/),
    ).toBeInTheDocument();

    expect(screen.getByRole("table", { name: "Video comments" })).toBeInTheDocument();
    expect(screen.getByText("Author One")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getAllByText("Example Video").length).toBeGreaterThan(0);
    });
    void user;
  });

  it("mounts the analytics and sampling panels when their sub-tabs are selected", async () => {
    setupDefaultMocks();
    const { user } = renderWithProviders(<CommentsBrowser videoId="v1" />);

    await user.click(screen.getByRole("tab", { name: "Analytics" }));
    expect(screen.getByText("Like-count distribution")).toBeInTheDocument();
    expect(screen.getByText("Comment velocity")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Sampling" }));
    expect(screen.getByText("Sampling workbench stub")).toBeInTheDocument();
  });

  it("opens the tree modal with the root id when a reply row is clicked", async () => {
    setupDefaultMocks({
      comments: [
        makeComment({
          comment_id: "child",
          parent_comment_id: "missing-parent",
          root_comment_id: "root-id",
          comment_text: "Nested reply",
        }),
      ],
    });
    const { user } = renderWithProviders(<CommentsBrowser videoId="v1" />);

    await user.click(screen.getByText("Nested reply"));
    expect(
      await screen.findByText("Comment tree modal for root-id"),
    ).toBeInTheDocument();
  });

  it("renders the single-thread view and the back link restores the comments tab", async () => {
    const replace = vi.fn();
    setupDefaultMocks({
      threadId: "t1",
      threads: [
        {
          comment: makeComment({
            comment_id: "t1",
            author_name: "Thread Author",
            comment_text: "Thread root",
          }),
          replies: [
            makeComment({
              comment_id: "t1r",
              parent_comment_id: "t1",
              author_name: "Replier",
              comment_text: "A reply",
            }),
          ],
        },
      ],
    });
    mockRouter.mockReturnValue({ replace } as unknown as ReturnType<typeof useRouter>);
    const { user } = renderWithProviders(<CommentsBrowser videoId="v1" />);

    expect(screen.getByText("Thread root")).toBeInTheDocument();
    expect(screen.getByText("A reply")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Back to all comments/ }));
    expect(replace).toHaveBeenCalledWith("/videos/v1?tab=comments");
  });

  it("shows a not-found state for an unknown thread id", () => {
    setupDefaultMocks({ threadId: "nope", threads: [] });
    renderWithProviders(<CommentsBrowser videoId="v1" />);
    expect(screen.getByText("Thread not found")).toBeInTheDocument();
  });
});
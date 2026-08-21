import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, makeCommentTree, makeComment } from "@/test-utils";
import { CommentTreeModal } from "@/components/features/comment-tree-modal";
import { ApiError } from "@/services/api";

vi.mock("@/hooks/useCommentTree", () => ({
  useCommentTree: vi.fn(),
}));

import { useCommentTree } from "@/hooks/useCommentTree";

const mockUseCommentTree = vi.mocked(useCommentTree);

function makeLoadingState() {
  mockUseCommentTree.mockReturnValue({
    data: undefined,
    isLoading: true,
    error: null,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof useCommentTree>);
}

function makeSuccessState(overrides = {}) {
  const node = makeCommentTree(overrides);
  mockUseCommentTree.mockReturnValue({
    data: node,
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof useCommentTree>);
  return node;
}

describe("CommentTreeModal", () => {
  beforeEach(() => {
    mockUseCommentTree.mockReset();
  });

  it("renders loading state when data is loading", () => {
    makeLoadingState();
    renderWithProviders(
      <CommentTreeModal open={true} onOpenChange={() => {}} videoId="v1" commentId="c1" />,
    );
    expect(screen.getByText("Loading comment thread…")).toBeInTheDocument();
  });

  it("renders error state and calls refetch on retry", async () => {
    const refetch = vi.fn();
    mockUseCommentTree.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("Server error"),
      refetch,
    } as unknown as ReturnType<typeof useCommentTree>);

    const user = userEvent.setup();
    renderWithProviders(
      <CommentTreeModal open={true} onOpenChange={() => {}} videoId="v1" commentId="c1" />,
    );
    expect(screen.getByText("Server error")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("renders empty state when no data returned", () => {
    mockUseCommentTree.mockReturnValue({
      data: null,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useCommentTree>);

    renderWithProviders(
      <CommentTreeModal open={true} onOpenChange={() => {}} videoId="v1" commentId="c1" />,
    );
    expect(screen.getByText("No replies in this thread")).toBeInTheDocument();
  });

  it("renders a friendly missing state for 404 errors", () => {
    mockUseCommentTree.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new ApiError(404, "Comment not found"),
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useCommentTree>);

    renderWithProviders(
      <CommentTreeModal open={true} onOpenChange={() => {}} videoId="v1" commentId="c1" />,
    );
    expect(screen.getByText("This comment is no longer available")).toBeInTheDocument();
    expect(screen.queryByText("Comment not found")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
  });

  it("keeps the retryable error state for non-404 failures", () => {
    mockUseCommentTree.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new ApiError(500, "Server exploded"),
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useCommentTree>);

    renderWithProviders(
      <CommentTreeModal open={true} onOpenChange={() => {}} videoId="v1" commentId="c1" />,
    );
    expect(screen.getByText("Server exploded")).toBeInTheDocument();
    expect(screen.queryByText("This comment is no longer available")).not.toBeInTheDocument();
  });

  it("shows comment thread when data is available", () => {
    makeSuccessState();
    renderWithProviders(
      <CommentTreeModal open={true} onOpenChange={() => {}} videoId="v1" commentId="c1" />,
    );
    expect(screen.getByText("Comment Thread")).toBeInTheDocument();
    expect(screen.getByText("Author One")).toBeInTheDocument();
    expect(screen.getByText("First comment text")).toBeInTheDocument();
  });

  it("shows thread summary in dialog description", () => {
    makeSuccessState({ total_replies: 5, max_depth: 3 });
    renderWithProviders(
      <CommentTreeModal open={true} onOpenChange={() => {}} videoId="v1" commentId="c1" />,
    );
    expect(screen.getByText(/Thread with 6 comments \(max depth: 3\)/)).toBeInTheDocument();
  });

  it("shows the total replies count on the start-sample button", () => {
    makeSuccessState({ total_replies: 3 });
    renderWithProviders(
      <CommentTreeModal open={true} onOpenChange={() => {}} videoId="v1" commentId="c1" />,
    );
    // The description says "Thread with 4 comments" and the button says "thread (4 comments)"
    expect(screen.getByText(/Start sample from thread/)).toBeInTheDocument();
    const buttons = screen.getAllByText(/4 comments/);
    expect(buttons.length).toBeGreaterThanOrEqual(1);
  });

  it("calls onStartSampleFromThread when start sample button is clicked", async () => {
    const onStartSample = vi.fn();
    const user = userEvent.setup();
    makeSuccessState({ total_replies: 2 });
    renderWithProviders(
      <CommentTreeModal
        open={true}
        onOpenChange={() => {}}
        videoId="v1"
        commentId="c1"
        onStartSampleFromThread={onStartSample}
      />,
    );
    await user.click(screen.getByRole("button", { name: /Start new sample from this thread/i }));
    expect(onStartSample).toHaveBeenCalledTimes(1);
  });

  it("does not show footer button when there are no replies", () => {
    makeSuccessState({ total_replies: 0 });
    renderWithProviders(
      <CommentTreeModal open={true} onOpenChange={() => {}} videoId="v1" commentId="c1" />,
    );
    expect(screen.queryByRole("button", { name: /Start new sample from this thread/i })).not.toBeInTheDocument();
  });
});

describe("CommentTreeModal: CommentNodeView", () => {
  it("renders nested replies", () => {
    const reply = makeCommentTree({
      comment: makeComment({
        comment_id: "r1",
        author_name: "Replier",
        comment_text: "A reply",
        is_reply: true,
        parent_comment_id: "c1",
      }),
    });
    makeSuccessState({
      replies: [reply],
      total_replies: 1,
    });
    renderWithProviders(
      <CommentTreeModal open={true} onOpenChange={() => {}} videoId="v1" commentId="c1" />,
    );
    expect(screen.getByText("Replier")).toBeInTheDocument();
    expect(screen.getByText("A reply")).toBeInTheDocument();
  });
});

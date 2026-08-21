import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test-utils";
import { CommentTree } from "@/components/features/comment-tree";
import type { Comment } from "@/lib/types";

function makeComment(overrides: Partial<Comment> = {}): Comment {
  return {
    comment_id: "c1",
    video_id: "v1",
    author_name: "Author",
    author_id: "a1",
    comment_text: "Root comment",
    published_at: "2024-01-01T10:00:00Z",
    is_reply: false,
    parent_comment_id: null,
    root_comment_id: null,
    is_author: false,
    first_observed_run_id: "r1",
    like_count: 5,
    reply_count: 0,
    is_removed: false,
    raw_json: {},
    ...overrides,
  };
}

describe("CommentTree", () => {
  it("shows empty state when no comments", () => {
    renderWithProviders(<CommentTree comments={[]} />);
    expect(screen.getByText("No comments to display.")).toBeInTheDocument();
  });

  it("renders a flat list of root comments", () => {
    const comments = [
      makeComment({ comment_id: "a", author_name: "Alice", comment_text: "First" }),
      makeComment({ comment_id: "b", author_name: "Bob", comment_text: "Second" }),
    ];
    renderWithProviders(<CommentTree comments={comments} />);
    expect(screen.getByText("Total comments: 2")).toBeInTheDocument();
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
  });

  it("organises nested replies under parents", () => {
    const comments = [
      makeComment({ comment_id: "root", parent_comment_id: null }),
      makeComment({ comment_id: "reply1", parent_comment_id: "root", comment_text: "Nested", is_reply: true, author_name: "Nester" }),
    ];
    renderWithProviders(<CommentTree comments={comments} />);
    expect(screen.getByText("Root comment")).toBeInTheDocument();
    expect(screen.getByText("Nested")).toBeInTheDocument();
  });

  it("displays uploader and reply badges", () => {
    const comments = [
      makeComment({ is_author: true, author_name: "Uploader" }),
      makeComment({ comment_id: "r1", is_reply: true, parent_comment_id: "c1", comment_text: "Reply content" }),
    ];
    renderWithProviders(<CommentTree comments={comments} />);
    expect(screen.getByText("uploader")).toBeInTheDocument();
    expect(screen.getByText("Reply")).toBeInTheDocument();
  });
});

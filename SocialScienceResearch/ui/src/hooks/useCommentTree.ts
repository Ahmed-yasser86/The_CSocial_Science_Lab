"use client";

import { useQuery } from "@tanstack/react-query";
import * as api from "@/services/api";

export interface CommentTreeNode {
  comment: {
    comment_id: string;
    video_id: string;
    author_name: string | null;
    author_id: string | null;
    comment_text: string | null;
    published_at: string | null;
    is_reply: boolean;
    parent_comment_id: string | null;
    root_comment_id: string | null;
    is_author: boolean | null;
    like_count: number | null;
    reply_count: number | null;
    is_removed: boolean | null;
    raw_json: Record<string, unknown>;
  };
  replies: CommentTreeNode[];
  total_replies: number;
  max_depth: number;
}

export function useCommentTree(videoId: string, commentId: string) {
  return useQuery({
    queryKey: ["commentTree", videoId, commentId] as const,
    queryFn: () => api.getCommentTree(videoId, commentId),
    enabled: !!videoId && !!commentId,
  });
}
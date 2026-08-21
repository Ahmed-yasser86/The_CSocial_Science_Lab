"use client";

import { useMemo, useState } from "react";
import { ChevronRight, ChevronDown, MessageSquare } from "lucide-react";
import type { Comment } from "@/lib/types";
import { formatDateTime, formatNumber } from "@/lib/format";

interface CommentTreeProps {
  comments: Comment[];
}

type CommentNode = Comment & { children: CommentNode[] };

function buildCommentTree(comments: Comment[]): CommentNode[] {
  const commentMap = new Map<string, CommentNode>();
  const roots: CommentNode[] = [];

  comments.forEach((c) => {
    commentMap.set(c.comment_id, { ...c, children: [] });
  });

  comments.forEach((c) => {
    const node = commentMap.get(c.comment_id)!;
    if (c.parent_comment_id) {
      const parent = commentMap.get(c.parent_comment_id);
      if (parent) {
        parent.children.push(node);
      } else {
        roots.push(node);
      }
    } else {
      roots.push(node);
    }
  });

  return roots;
}

function CommentNode({
  comment,
  depth = 0,
}: {
  comment: CommentNode;
  depth?: number;
}) {
  const [expanded, setExpanded] = useState(true);

  const hasChildren = comment.children.length > 0;

  return (
    <div
      style={{ marginLeft: depth * 24 }}
      className="border-l-2 border-border/50 pl-3 py-2"
    >
      <div className="flex items-start gap-2">
        {hasChildren && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex h-6 w-6 items-center justify-center text-muted-foreground hover:text-foreground transition-colors"
            aria-label={expanded ? "Collapse" : "Expand"}
            aria-expanded={expanded}
          >
            {expanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
          </button>
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap gap-y-1">
            <MessageSquare className="size-3.5 text-muted-foreground" aria-hidden />
            <span className="font-medium truncate">
              {comment.author_name ?? comment.author_id ?? "anonymous"}
            </span>
            {comment.is_author && (
              <span className="text-xs px-1.5 py-0.5 bg-primary/10 text-primary rounded">
                uploader
              </span>
            )}
            {comment.is_reply && (
              <span className="text-xs px-1.5 py-0.5 bg-muted text-muted-foreground rounded">
                Reply
              </span>
            )}
            <span className="text-xs text-muted-foreground">
              {comment.published_at ? formatDateTime(comment.published_at) : "—"}
            </span>
          </div>
          <div className="mt-1 text-sm line-clamp-3 text-muted-foreground">
            {comment.comment_text ?? "—"}
          </div>
          {expanded && comment.children.length > 0 && (
            <div className="mt-2 space-y-2">
              {comment.children.map((child) => (
                <CommentNode key={child.comment_id} comment={child} depth={depth + 1} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function CommentTree({ comments }: CommentTreeProps) {
  const tree = useMemo(() => buildCommentTree(comments), [comments]);

  if (comments.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No comments to display.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm text-muted-foreground mb-4">
        <span>Total comments: {formatNumber(comments.length)}</span>
      </div>
      <div className="space-y-2">
        {tree.map((root) => (
          <CommentNode key={root.comment_id} comment={root} />
        ))}
      </div>
    </div>
  );
}
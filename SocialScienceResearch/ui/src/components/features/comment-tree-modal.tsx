"use client";

import { useState } from "react";
import { MessageSquare, ChevronRight, ChevronDown, Loader2, GitBranch } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useCommentTree, type CommentTreeNode } from "@/hooks/useCommentTree";
import { ApiError } from "@/services/api";
import { formatDateTime, formatNumber } from "@/lib/format";

interface CommentTreeModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  videoId: string;
  commentId: string;
  onStartSampleFromThread?: (commentIds: string[]) => void;
}

function CommentNodeView({
  node,
  depth = 0,
  onSampleThread,
}: {
  node: CommentTreeNode;
  depth?: number;
  onSampleThread?: (commentIds: string[]) => void;
}) {
  const [expanded, setExpanded] = useState(depth === 0);
  const [loading] = useState(false);
  const [fullTree] = useState<CommentTreeNode | null>(null);

  const hasChildren = node.replies.length > 0 || node.total_replies > node.replies.length;
  const treeToRender = fullTree || node;
  const childrenToRender = treeToRender.replies;

  const handleExpand = async () => {
    if (fullTree) {
      setExpanded(!expanded);
      return;
    }
    if (!hasChildren || !expanded) {
      setExpanded(!expanded);
      return;
    }
    setExpanded(!expanded);
  };

  const handleStartSample = () => {
    const commentIds = collectCommentIds(node);
    onSampleThread?.(commentIds);
  };

  return (
    <div style={{ marginLeft: depth * 24 }} className="py-1">
      <div className="flex items-start gap-2">
        {hasChildren || loading ? (
          <button
            onClick={handleExpand}
            disabled={loading}
            className="flex h-6 w-6 items-center justify-center text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50 flex-shrink-0 mt-1"
            aria-label={expanded ? "Collapse" : "Expand"}
          >
            {loading ? (
              <Loader2 className="size-4 animate-spin" />
            ) : expanded ? (
              <ChevronDown className="size-4" />
            ) : (
              <ChevronRight className="size-4" />
            )}
          </button>
        ) : (
          <div className="w-6 flex-shrink-0" />
        )}

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <MessageSquare className="size-3.5 text-muted-foreground" aria-hidden />
            <span className="font-medium text-sm">
              {node.comment.author_name ?? node.comment.author_id ?? "anonymous"}
            </span>
            {node.comment.is_author && (
              <Badge variant="secondary" className="text-xs">uploader</Badge>
            )}
            {node.comment.is_reply && (
              <Badge variant="outline" className="text-xs">reply</Badge>
            )}
            <span className="text-xs text-muted-foreground">
              {node.comment.published_at ? formatDateTime(node.comment.published_at) : "—"}
            </span>
            {node.comment.like_count !== null && node.comment.like_count !== undefined && (
              <span className="text-xs text-muted-foreground">
                <span className="font-mono tabular-nums">{formatNumber(node.comment.like_count)}</span> likes
              </span>
            )}
            {node.comment.reply_count !== null && node.comment.reply_count !== undefined && node.comment.reply_count > 0 && (
              <span className="text-xs text-muted-foreground">
                <span className="font-mono tabular-nums">{formatNumber(node.comment.reply_count)}</span> replies
              </span>
            )}
            {node.comment.is_removed && (
              <Badge variant="destructive" className="text-xs">removed</Badge>
            )}
          </div>

          <div className="mt-1 text-sm text-muted-foreground line-clamp-3">
            {node.comment.comment_text ?? "—"}
          </div>

          {depth === 0 && node.total_replies > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="mt-2 h-7 text-xs"
              onClick={handleStartSample}
            >
              <GitBranch className="size-3.5 mr-1" />
              Start sample from thread ({formatNumber(node.total_replies + 1)} comments)
            </Button>
          )}

          {expanded && childrenToRender.length > 0 && (
            <div className="mt-2">
              {childrenToRender.map((child) => (
                <CommentNodeView
                  key={child.comment.comment_id}
                  node={child}
                  depth={depth + 1}
                  onSampleThread={onSampleThread}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function collectCommentIds(node: CommentTreeNode): string[] {
  const ids = [node.comment.comment_id];
  for (const child of node.replies) {
    ids.push(...collectCommentIds(child));
  }
  return ids;
}

function EmptyTreeState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <MessageSquare className="size-12 text-muted-foreground/50 mb-3" aria-hidden />
      <p className="text-sm font-medium text-muted-foreground">No replies in this thread</p>
      <p className="text-xs text-muted-foreground mt-1">This comment has no replies yet</p>
    </div>
  );
}

function MissingTreeState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <MessageSquare className="size-12 text-muted-foreground/50 mb-3" aria-hidden />
      <p className="text-sm font-medium">This comment is no longer available</p>
      <p className="text-xs text-muted-foreground mt-1">
        The comment record could not be found in the video&apos;s comment store.
      </p>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="flex items-center justify-center py-12">
      <Loader2 className="size-6 animate-spin text-muted-foreground" />
      <span className="ml-2 text-sm text-muted-foreground">Loading comment thread…</span>
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <p className="text-sm text-destructive">{message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" className="mt-3" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

export function CommentTreeModal({
  open,
  onOpenChange,
  videoId,
  commentId,
  onStartSampleFromThread,
}: CommentTreeModalProps) {
  const { data, isLoading, error, refetch } = useCommentTree(videoId, commentId);

  const handleStartSample = () => {
    if (data) {
      const commentIds = collectCommentIds(data);
      onStartSampleFromThread?.(commentIds);
    }
  };

  const totalComments = data ? data.total_replies + 1 : 0;
  const maxDepth = data?.max_depth ?? 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <MessageSquare className="size-5" aria-hidden />
            Comment Thread
          </DialogTitle>
          <DialogDescription>
            {data
              ? `Thread with ${formatNumber(totalComments)} comments (max depth: ${maxDepth})`
              : "View the full reply hierarchy for this comment"}
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="flex-1 -mx-2 px-2">
          {isLoading && <LoadingState />}
          {!isLoading && error instanceof ApiError && error.status === 404 && <MissingTreeState />}
          {!isLoading && !(error instanceof ApiError && error.status === 404) && error && (
            <ErrorState
              message={error instanceof Error ? error.message : "Failed to load comment tree"}
              onRetry={() => refetch()}
            />
          )}
          {!isLoading && !error && !data && <EmptyTreeState />}
          {!isLoading && !error && data && (
            <div className="border-l-2 border-border/50 ml-2 pl-3 py-2">
              <CommentNodeView
                node={data}
                depth={0}
                onSampleThread={onStartSampleFromThread}
              />
            </div>
          )}
        </ScrollArea>

        {data && data.total_replies > 0 && (
          <DialogFooter>
            <Button
              variant="outline"
              onClick={handleStartSample}
              className="w-full"
            >
              <GitBranch className="size-4 mr-2" />
              Start new sample from this thread
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}
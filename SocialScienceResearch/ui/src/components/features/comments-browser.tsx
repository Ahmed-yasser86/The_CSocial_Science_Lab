"use client";

import { useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { MessageSquare, ArrowLeft } from "lucide-react";
import type { Comment, Video } from "@/lib/types";
import { useQuery } from "@tanstack/react-query";
import {
  useVideoComments,
  useCommentPercentiles,
  useCommentVelocity,
  useSampleComments,
  useCommentThreads,
} from "@/services/queries";
import * as api from "@/services/api";
import { DataTable, type Column } from "@/components/features/data-table";
import {
  LoadingState,
  ErrorState,
  EmptyState,
} from "@/components/features/state";
import { ChartCard, HistogramChart, TimelineChart } from "@/components/features/charts";
import { SamplingWorkbench } from "@/components/features/sampling/SamplingWorkbench";
import { AvailabilityBadge } from "@/components/features/availability-badge";
import { Badge } from "@/components/ui/badge";
import { CommentTree } from "@/components/features/comment-tree";
import { CommentTreeModal } from "@/components/features/comment-tree-modal";
import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatDateTime, formatNumber } from "@/lib/format";
import Link from "next/link";
import { Button } from "@/components/ui/button";

const BAND_ORDER = ["75", "90", "95", "99"];

type SubTab = "comments" | "analytics" | "sampling";

export function resolveTreeRootId(comment: Comment): string {
  return comment.root_comment_id ?? comment.comment_id;
}

function VideoTitleBar({ videoId, video }: { videoId: string; video?: Video }) {
  if (!video) return null;
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md border bg-muted/30 p-3">
      <Link href={`/videos/${videoId}`} className="flex items-center gap-2">
        <MessageSquare className="size-4 text-muted-foreground" aria-hidden />
        <span className="font-medium truncate max-w-xs">{video.title}</span>
      </Link>
      <span className="text-xs text-muted-foreground">by</span>
      <span className="font-mono text-xs text-primary">{video.channel_id}</span>
    </div>
  );
}

export function CommentsBrowser({ videoId }: { videoId: string }) {
  const [bucket, setBucket] = useState<"day" | "hour">("day");
  const [subTab, setSubTab] = useState<SubTab>("comments");
  const [commentModal, setCommentModal] = useState<{ commentId: string } | null>(null);
  const searchParams = useSearchParams();
  const router = useRouter();
  const threadId = searchParams.get("thread");

  const commentsQuery = useVideoComments(videoId);
  const percentilesQuery = useCommentPercentiles(videoId);
  const velocityQuery = useCommentVelocity(videoId, bucket);
  const sampleMutation = useSampleComments(videoId);
  const threadsQuery = useCommentThreads(videoId);

  const videoQuery = useQuery({
    queryKey: ["video", videoId],
    queryFn: () => api.getVideo(videoId),
    enabled: !!videoId,
  });

  const video = videoQuery.data;
  const comments = commentsQuery.data ?? [];
  const rootCount = comments.filter((c) => !c.is_reply).length;
  const replyCount = comments.length - rootCount;

  const columns: Column<Comment>[] = [
    {
      key: "author",
      header: "Author",
      sortable: true,
      sortValue: (c) => c.author_name ?? "",
      cell: (c) => (
        <span className="flex items-center gap-1.5">
          {c.is_author ? <Badge variant="secondary">uploader</Badge> : null}
          <span className="font-medium">{c.author_name ?? c.author_id ?? "anonymous"}</span>
        </span>
      ),
    },
    {
      key: "comment_text",
      header: "Comment",
      cell: (c) => (
        <span className="line-clamp-2 max-w-xl text-sm cursor-pointer hover:underline">{c.comment_text ?? "—"}</span>
      ),
    },
    {
      key: "published_at",
      header: "Published",
      sortable: true,
      sortValue: (c) => c.published_at ?? "",
      cell: (c) => formatDateTime(c.published_at),
    },
    {
      key: "like_count",
      header: "Likes",
      sortable: true,
      sortValue: (c) => c.like_count ?? -1,
      cell: (c) => (
        <span className="font-mono tabular-nums">
          {c.like_count !== null && c.like_count !== undefined
            ? formatNumber(c.like_count)
            : "—"}
        </span>
      ),
    },
    {
      key: "reply_count",
      header: "Replies",
      sortable: true,
      sortValue: (c) => c.reply_count ?? -1,
      cell: (c) => (
        <span className="font-mono tabular-nums">
          {c.reply_count !== null && c.reply_count !== undefined
            ? formatNumber(c.reply_count)
            : "—"}
        </span>
      ),
    },
    {
      key: "is_removed",
      header: "Removed",
      sortable: true,
      sortValue: (c) => (c.is_removed ? 1 : 0),
      cell: (c) =>
        c.is_removed ? (
          <Badge variant="destructive" className="text-xs">removed</Badge>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    {
      key: "thread",
      header: "Thread",
      sortable: true,
      sortValue: (c) => (c.is_reply ? "reply" : "root"),
      cell: (c) => (
        <Badge variant="outline">{c.is_reply ? "reply" : "root"}</Badge>
      ),
    },
    {
      key: "video",
      header: "Video",
      cell: (c) => (
        <Link
          href={`/videos/${c.video_id}`}
          className="text-primary underline-offset-2 hover:underline text-sm"
        >
          {video?.title ?? c.video_id}
        </Link>
      ),
    },
  ];

  const bands = percentilesQuery.data;

  function handleCommentClick(comment: Comment) {
    setCommentModal({ commentId: resolveTreeRootId(comment) });
  }

  function handleBackToAll() {
    router.replace(`/videos/${videoId}?tab=comments`);
  }

  const summaryLine = commentsQuery.isLoading
    ? "Loading comments…"
    : `${formatNumber(comments.length)} comments collected · ${formatNumber(rootCount)} roots · ${formatNumber(replyCount)} replies`;

  if (threadId) {
    const threadData = threadsQuery.data ?? [];
    const thread = threadData.find((t) => t.comment.comment_id === threadId);

    if (!thread) {
      return (
        <div className="space-y-6">
          <VideoTitleBar videoId={videoId} video={video} />
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={handleBackToAll}>
              <ArrowLeft className="size-3.5" aria-hidden />
              Back to all comments
            </Button>
          </div>
          <ErrorState
            message="Thread not found"
            detail="The requested comment thread could not be found."
          />
        </div>
      );
    }

    return (
      <div className="space-y-6">
        <VideoTitleBar videoId={videoId} video={video} />
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={handleBackToAll}>
            <ArrowLeft className="size-3.5" aria-hidden />
            Back to all comments
          </Button>
        </div>
        <section aria-label="Comment thread">
          <h2 className="mb-3 text-sm font-medium">Thread</h2>
          {threadsQuery.isLoading ? (
            <LoadingState label="Loading thread…" />
          ) : threadsQuery.isError ? (
            <ErrorState message={(threadsQuery.error as Error).message} />
          ) : (
            <CommentTree comments={[thread.comment, ...thread.replies]} />
          )}
        </section>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <header className="space-y-3">
        <VideoTitleBar videoId={videoId} video={video} />
        <p className="px-1 text-sm text-muted-foreground">{summaryLine}</p>
      </header>

      <Tabs value={subTab} onValueChange={(value) => setSubTab(value as SubTab)} className="w-full">
        <TabsList>
          <TabsTrigger value="comments">All Comments</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
          <TabsTrigger value="sampling">Sampling</TabsTrigger>
        </TabsList>

        <TabsContent value="comments" className="mt-6">
          <section aria-label="All comments" className="space-y-4">
            <div>
              <h2 className="text-sm font-medium">All comments</h2>
              <p className="mt-1 text-xs text-muted-foreground">
                Click any row to open its full reply thread.
              </p>
            </div>
            {commentsQuery.isLoading ? (
              <LoadingState label="Loading comments…" />
            ) : commentsQuery.isError ? (
              <ErrorState message={(commentsQuery.error as Error).message} retry={() => commentsQuery.refetch()} />
            ) : (
              <DataTable
                columns={columns}
                rows={commentsQuery.data ?? []}
                getRowKey={(c) => c.comment_id}
                initialSortKey="published_at"
                initialSortDirection="desc"
                emptyTitle="No comments collected"
                emptyDescription="Collect the video with comment collection enabled to build this population."
                ariaLabel="Video comments"
                onRowClick={handleCommentClick}
              />
            )}
          </section>
        </TabsContent>

        <TabsContent value="analytics" className="mt-6">
          <section aria-label="Comment analytics" className="space-y-4">
            <div>
              <h2 className="text-sm font-medium">Analytics</h2>
              <p className="mt-1 text-xs text-muted-foreground">
                Like-count distribution and comment velocity for this video.
              </p>
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <ChartCard
                title="Like-count distribution"
                description="Histogram of each comment's latest observed like count, with percentile bands."
              >
                {percentilesQuery.isLoading ? (
                  <LoadingState label="Computing percentiles…" />
                ) : percentilesQuery.isError ? (
                  <ErrorState message={(percentilesQuery.error as Error).message} />
                ) : bands && bands.availability === "missing" ? (
                  <EmptyState
                    title="No observed comment like counts"
                    description="Percentile bands require at least one comment with an observed like count."
                  />
                ) : bands ? (
                  <div className="space-y-3">
                    <HistogramChart
                      percentiles={bands}
                      ariaLabel="Distribution of comment like counts with percentile bands"
                    />
                    <div className="flex flex-wrap items-center gap-2">
                      <AvailabilityBadge availability={bands.availability} />
                      {BAND_ORDER.map((band) => (
                        <Badge key={band} variant="outline">
                          P{band}:{" "}
                          {bands.bands[band] === null || bands.bands[band] === undefined
                            ? "—"
                            : formatNumber(bands.bands[band])}
                        </Badge>
                      ))}
                      <span className="text-xs text-muted-foreground">
                        n = {formatNumber(bands.observed_like_counts.length)}
                      </span>
                    </div>
                  </div>
                ) : null}
              </ChartCard>

              <ChartCard
                title="Comment velocity"
                description="Comments published per time bucket. Records without a timestamp are counted separately."
              >
                <div className="mb-2 flex items-center justify-between">
                  <Select
                    value={bucket}
                    onValueChange={(v) => setBucket(v as "day" | "hour")}
                    items={[
                      { value: "day", label: "Per day" },
                      { value: "hour", label: "Per hour" },
                    ]}
                  >
                    <SelectTrigger size="sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="w-[--anchor-width]">
                      <SelectItem value="day">Per day</SelectItem>
                      <SelectItem value="hour">Per hour</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {velocityQuery.isLoading ? (
                  <LoadingState label="Computing velocity…" />
                ) : velocityQuery.isError ? (
                  <ErrorState message={(velocityQuery.error as Error).message} />
                ) : velocityQuery.data && velocityQuery.data.length > 0 ? (
                  <TimelineChart
                    data={velocityQuery.data}
                    ariaLabel={`Comment publication timeline by ${bucket}`}
                  />
                ) : (
                  <EmptyState
                    icon={MessageSquare}
                    title="No comment timestamps"
                    description="Comments have not been collected for this video."
                  />
                )}
              </ChartCard>
            </div>
          </section>
        </TabsContent>

        <TabsContent value="sampling" className="mt-6">
          <section aria-label="Comment sampling" className="space-y-4">
            <div>
              <h2 className="text-sm font-medium">Sampling</h2>
              <p className="mt-1 text-xs text-muted-foreground">
                Build a sample of comments from this video&apos;s population.
              </p>
            </div>
            <SamplingWorkbench
              entityType="comment"
              populationSize={comments.length}
              mutate={sampleMutation}
            />
          </section>
        </TabsContent>
      </Tabs>

      {commentModal && (
        <CommentTreeModal
          open={!!commentModal}
          onOpenChange={(open) => open || setCommentModal(null)}
          videoId={videoId}
          commentId={commentModal.commentId}
        />
      )}
    </div>
  );
}
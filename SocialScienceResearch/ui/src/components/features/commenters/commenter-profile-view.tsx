"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { EmptyState, ErrorState, LoadingState } from "@/components/features/state";
import { DataTable, type Column } from "@/components/features/data-table";
import { useCommenterProfile } from "@/services/commenters";
import { formatNumber, formatDate } from "@/lib/format";
import type {
  ProfileChannelRow,
  ProfileVideoRow,
} from "@/lib/commenter-overlap-types";

const videoColumns: Column<ProfileVideoRow>[] = [
  {
    key: "video_id",
    header: "Video",
    cell: (v) => (
      <Link
        href={`/network/videos/${encodeURIComponent(v.video_id)}`}
        className="font-medium underline underline-offset-2 hover:text-foreground"
      >
        {v.video_id}
      </Link>
    ),
    sortValue: (v) => v.video_id,
  },
  {
    key: "channel_name",
    header: "Channel",
    cell: (v) => v.channel_name ?? v.channel_id ?? "–",
    sortValue: (v) => v.channel_name ?? v.channel_id ?? "",
  },
  {
    key: "comment_count",
    header: "Comments",
    cell: (v) => v.comment_count,
    sortValue: (v) => v.comment_count,
    className: "text-right",
    headerClassName: "text-right",
  },
  {
    key: "root_count",
    header: "Roots",
    cell: (v) => v.root_count,
    sortValue: (v) => v.root_count,
    className: "text-right",
    headerClassName: "text-right",
  },
  {
    key: "reply_count",
    header: "Replies",
    cell: (v) => v.reply_count,
    sortValue: (v) => v.reply_count,
    className: "text-right",
    headerClassName: "text-right",
  },
  {
    key: "last_seen_at",
    header: "Last seen",
    cell: (v) => formatDate(v.last_seen_at),
    sortValue: (v) => v.last_seen_at ?? null,
    className: "text-right",
    headerClassName: "text-right",
  },
];

const channelColumns: Column<ProfileChannelRow>[] = [
  {
    key: "channel_id",
    header: "Channel",
    cell: (c) => c.channel_name ?? c.channel_id,
    sortValue: (c) => c.channel_name ?? c.channel_id,
  },
  {
    key: "comment_count",
    header: "Comments",
    cell: (c) => c.comment_count,
    sortValue: (c) => c.comment_count,
    className: "text-right",
    headerClassName: "text-right",
  },
  {
    key: "video_count",
    header: "Videos",
    cell: (c) => c.video_count,
    sortValue: (c) => c.video_count,
    className: "text-right",
    headerClassName: "text-right",
  },
  {
    key: "root_count",
    header: "Roots",
    cell: (c) => c.root_count,
    sortValue: (c) => c.root_count,
    className: "text-right",
    headerClassName: "text-right",
  },
  {
    key: "reply_count",
    header: "Replies",
    cell: (c) => c.reply_count,
    sortValue: (c) => c.reply_count,
    className: "text-right",
    headerClassName: "text-right",
  },
];

export function CommenterProfileView({
  authorKey,
  videoIds,
  channelIds,
}: {
  authorKey: string;
  videoIds?: string[];
  channelIds?: string[];
}) {
  const [tab, setTab] = useState<"videos" | "channels" | "comments">("videos");
  const searchParams = useSearchParams();
  const scopeVideoIds =
    videoIds ??
    (searchParams.get("video_ids") ?? "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  const scopeChannelIds =
    channelIds ??
    (searchParams.get("channel_ids") ?? "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  const query = useCommenterProfile(authorKey, scopeVideoIds, scopeChannelIds);

  if (query.isLoading) {
    return <LoadingState label="Loading commenter profile…" />;
  }
  if (query.isError) {
    return (
      <ErrorState
        message={
          query.error instanceof Error ? query.error.message : "Request failed"
        }
        retry={() => query.refetch()}
      />
    );
  }
  const profile = query.data;
  if (!profile) return <EmptyState title="No profile found" />;

  return (
    <div className="space-y-6" data-testid="commenter-profile">
      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <h2 className="text-lg font-semibold">
            {profile.author_name ?? profile.author_key}
          </h2>
          <Badge variant="outline" className="text-[10px]">
            {profile.identity_kind === "id" ? "id-backed" : "name-only"}
          </Badge>
          {profile.is_author ? (
            <Badge variant="outline" className="text-[10px]">
              channel author
            </Badge>
          ) : null}
          <span className="text-xs text-muted-foreground">
            {profile.author_key}
          </span>
        </div>
        <dl className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Stat label="Comments" value={formatNumber(profile.total_comments)} />
          <Stat label="Videos" value={formatNumber(profile.video_count)} />
          <Stat label="Channels" value={formatNumber(profile.channel_count)} />
          <Stat label="First seen" value={formatDate(profile.first_seen_at)} />
        </dl>
      </Card>

      <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)}>
        <TabsList aria-label="Profile sections">
          <TabsTrigger value="videos">Videos ({profile.videos.length})</TabsTrigger>
          <TabsTrigger value="channels">
            Channels ({profile.channels.length})
          </TabsTrigger>
          <TabsTrigger value="comments">
            Comments ({profile.comments.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="videos" className="mt-4">
          {profile.videos.length ? (
            <DataTable
              columns={videoColumns}
              rows={profile.videos}
              getRowKey={(v) => v.video_id}
              initialSortKey="comment_count"
              initialSortDirection="desc"
              ariaLabel="Commenter videos"
            />
          ) : (
            <EmptyState title="No videos" />
          )}
        </TabsContent>

        <TabsContent value="channels" className="mt-4">
          {profile.channels.length ? (
            <DataTable
              columns={channelColumns}
              rows={profile.channels}
              getRowKey={(c) => c.channel_id}
              initialSortKey="comment_count"
              initialSortDirection="desc"
              ariaLabel="Commenter channels"
            />
          ) : (
            <EmptyState title="No channels" />
          )}
        </TabsContent>

        <TabsContent value="comments" className="mt-4">
          {profile.comments.length ? (
            <ul className="divide-y divide-border rounded-lg border border-border">
              {profile.comments.map((comment) => (
                <li key={comment.comment_id} className="p-3">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                    <Link
                      href={`/network/videos/${encodeURIComponent(comment.video_id)}`}
                      className="font-medium text-foreground underline underline-offset-2"
                    >
                      {comment.video_id}
                    </Link>
                    <span>{formatDate(comment.published_at)}</span>
                    {comment.is_reply ? (
                      <Badge variant="outline" className="text-[10px]">
                        reply
                      </Badge>
                    ) : null}
                    {comment.like_count !== null &&
                    comment.like_count !== undefined ? (
                      <span className="tabular-nums">
                        {comment.like_count} likes
                      </span>
                    ) : null}
                  </div>
                  {comment.comment_text ? (
                    <p className="mt-1 line-clamp-2 text-sm">{comment.comment_text}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title="No comments in scope" />
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-0.5 text-lg font-semibold tabular-nums">{value}</dd>
    </div>
  );
}

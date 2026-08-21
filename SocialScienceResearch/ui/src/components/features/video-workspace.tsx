"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useVideo, useVideoEngagement } from "@/services/queries";
import { MetricTile } from "@/components/features/metric-tile";
import { LoadingState, ErrorState, EmptyState } from "@/components/features/state";
import { CommentsBrowser } from "@/components/features/comments-browser";
import { RecommendationsExplorer } from "@/components/features/recommendations-explorer";
import { EgoNetworkView } from "@/components/features/ego-network-view";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { formatDate, formatDuration } from "@/lib/format";

type TabId = "overview" | "network" | "engagement" | "comments" | "recommendations";

export function VideoWorkspace({
  videoId,
  initialTab = "overview",
}: {
  videoId: string;
  initialTab?: TabId;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [tab, setTab] = useState<TabId>(initialTab);

  const videoQuery = useVideo(videoId);
  const engagementQuery = useVideoEngagement(videoId);

  function onTabChange(value: string) {
    setTab(value as TabId);
    router.replace(value === "overview" ? pathname : `${pathname}?tab=${value}`);
  }

  const video = videoQuery.data;

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="text-lg font-semibold">
          {video?.title ?? videoId}
        </h1>
        <code className="text-xs text-muted-foreground">video</code>
      </header>

      <Tabs value={tab} onValueChange={onTabChange} className="w-full">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="network">Network</TabsTrigger>
          <TabsTrigger value="engagement">Engagement</TabsTrigger>
          <TabsTrigger value="comments">Comments</TabsTrigger>
          <TabsTrigger value="recommendations">Recommendations</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-4">
          {videoQuery.isLoading ? (
            <LoadingState label="Loading video…" />
          ) : videoQuery.isError ? (
            <ErrorState message={(videoQuery.error as Error).message} />
          ) : video ? (
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
              <Card className="space-y-3 p-4">
                {video.thumbnail_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={video.thumbnail_url}
                    alt=""
                    className="aspect-video w-full rounded-md object-cover"
                    width={1280}
                    height={720}
                  />
                ) : null}
                <p className="text-sm text-muted-foreground">{video.description ?? "No description."}</p>
                <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                  <Meta label="Published" value={formatDate(video.upload_date)} />
                  <Meta label="Duration" value={formatDuration(video.duration)} />
                  <Meta label="Language" value={video.language ?? "—"} />
                  <Meta
                    label="Channel"
                    value={
                      video.channel_id ? (
                        <Link
                          href={`/channels/${video.channel_id}`}
                          className="font-mono text-primary underline-offset-2 hover:underline"
                        >
                          {video.channel_id}
                        </Link>
                      ) : (
                        "—"
                      )
                    }
                  />
                  <Meta label="First observed" value={<code className="text-xs">{video.first_observed_run_id}</code>} />
                  <Meta label="Age limit" value={video.age_limit === null ? "—" : `+${video.age_limit}`} />
                </dl>
                {video.tags?.length ? (
                  <div className="flex flex-wrap gap-1">
                    {video.tags.map((tag) => (
                      <Badge key={tag} variant="secondary">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                ) : null}
              </Card>

              <div className="space-y-3">
                <p className="text-xs text-muted-foreground">
                  Publication facts (from the source) are shown above.
                  Engagement statistics are separate observations and appear on
                  the Engagement tab.
                </p>
              </div>
            </div>
          ) : (
            <EmptyState title="Video not found" />
          )}
        </TabsContent>

        <TabsContent value="network" className="mt-4">
          <EgoNetworkView videoId={videoId} />
        </TabsContent>

        <TabsContent value="engagement" className="mt-4">
          {engagementQuery.isLoading ? (
            <LoadingState label="Loading engagement…" />
          ) : engagementQuery.isError ? (
            <ErrorState message={(engagementQuery.error as Error).message} />
          ) : engagementQuery.data ? (
            <div className="space-y-4">
              <h2 id="video-engagement-heading" className="sr-only">
                Engagement metrics
              </h2>
              <div
                className="grid gap-3 sm:grid-cols-3"
                role="group"
                aria-labelledby="video-engagement-heading"
              >
                <MetricTile label="Views" value={engagementQuery.data.views} observedAt={engagementQuery.data.observed_at} />
                <MetricTile label="Likes" value={engagementQuery.data.likes} observedAt={engagementQuery.data.observed_at} />
                <MetricTile label="Comments" value={engagementQuery.data.comments} observedAt={engagementQuery.data.observed_at} />
              </div>
              <h2 id="video-rates-heading" className="sr-only">
                Engagement rates
              </h2>
              <div
                className="grid gap-3 sm:grid-cols-3"
                role="group"
                aria-labelledby="video-rates-heading"
              >
                <RateTile label="Engagement rate" value={engagementQuery.data.engagement_rate} />
                <RateTile label="Like rate" value={engagementQuery.data.like_rate} />
                <RateTile label="Comment rate" value={engagementQuery.data.comment_rate} />
              </div>
              <p className="text-xs text-muted-foreground">
                Rates are (likes + comments) / views. A missing denominator
                yields an explicit “unsupported” availability — nothing is
                estimated.
              </p>
            </div>
          ) : (
            <EmptyState
              title="No engagement data"
              description="Collect this video to record its statistics."
            />
          )}
        </TabsContent>

        <TabsContent value="comments" className="mt-4">
          <CommentsBrowser videoId={videoId} />
        </TabsContent>

        <TabsContent value="recommendations" className="mt-4">
          <RecommendationsExplorer videoId={videoId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-0.5">{value}</dd>
    </div>
  );
}

function RateTile({ label, value }: { label: string; value?: { value: number | null } | null }) {
  return (
    <Card className="flex items-center justify-between p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="text-lg font-semibold tabular-nums">
        {!value || value.value === null ? "—" : `${(value.value * 100).toFixed(2)}%`}
      </p>
    </Card>
  );
}

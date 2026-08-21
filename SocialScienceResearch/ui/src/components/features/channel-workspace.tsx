"use client";

import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useChannelOverview, useChannelVideoCount, useSampleVideos, useChannels } from "@/services/queries";
import { MetricTile } from "@/components/features/metric-tile";
import { LoadingState, ErrorState, EmptyState } from "@/components/features/state";
import { VideoCorpusBrowser } from "@/components/features/video-corpus-browser";
import { SamplingWorkbench } from "@/components/features/sampling/SamplingWorkbench";
import { FoldersTab } from "@/components/features/folders-tab";
import { ExportTab } from "@/components/features/export-tab";
import { ChannelNetworkView } from "@/components/features/channel-network-view";

type TabId = "overview" | "network" | "videos" | "sampling" | "folders" | "export";

export function ChannelWorkspace({
  channelId,
  initialTab = "overview",
  searchParams = {},
}: {
  channelId: string;
  initialTab?: TabId;
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [tab, setTab] = useState<TabId>(initialTab);

  const overviewQuery = useChannelOverview(channelId);
  const countQuery = useChannelVideoCount(channelId);
  const sampleMutation = useSampleVideos(channelId);
  const channelsQuery = useChannels();
  const channelTitle =
    channelsQuery.data?.find((c) => c.channel_id === channelId)?.title ?? null;

  function onTabChange(value: string) {
    setTab(value as TabId);
    router.replace(value === "overview" ? pathname : `${pathname}?tab=${value}`);
  }

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="text-lg font-semibold">{channelTitle ?? channelId}</h1>
        {channelTitle ? (
          <code className="text-xs text-muted-foreground">channel {channelId}</code>
        ) : (
          <code className="text-xs text-muted-foreground">channel</code>
        )}
      </header>

      <Tabs value={tab} onValueChange={onTabChange} className="w-full">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="network">Network</TabsTrigger>
          <TabsTrigger value="videos">Videos</TabsTrigger>
          <TabsTrigger value="sampling">Sampling</TabsTrigger>
          <TabsTrigger value="folders">Folders</TabsTrigger>
          <TabsTrigger value="export">Export</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-4">
          {overviewQuery.isLoading ? (
            <LoadingState label="Loading channel overview…" />
          ) : overviewQuery.isError ? (
            <ErrorState
              message={(overviewQuery.error as Error).message}
              detail="The channel may not have been collected yet."
            />
          ) : overviewQuery.data ? (
            <div className="space-y-4">
              <h2 id="channel-stats-heading" className="sr-only">
                Channel statistics
              </h2>
              <div
                className="grid gap-3 sm:grid-cols-3"
                role="group"
                aria-labelledby="channel-stats-heading"
              >
                <MetricTile
                  label="Subscribers"
                  value={overviewQuery.data.subscriber_count}
                  observedAt={overviewQuery.data.observed_at}
                />
                <MetricTile
                  label="Videos"
                  value={overviewQuery.data.video_count}
                  observedAt={overviewQuery.data.observed_at}
                />
                <MetricTile
                  label="Views"
                  value={overviewQuery.data.view_count}
                  observedAt={overviewQuery.data.observed_at}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Latest observed statistics. Values the collector did not provide
                are shown as &ldquo;&mdash;&rdquo; with their availability, never as zero.
              </p>
            </div>
          ) : (
            <EmptyState
              title="No channel overview"
              description="Collect this channel to record its latest statistics."
            />
          )}
        </TabsContent>

        <TabsContent value="videos" className="mt-4">
          <VideoCorpusBrowser channelId={channelId} searchParams={searchParams} />
        </TabsContent>

        <TabsContent value="network" className="mt-4">
          <ChannelNetworkView channelId={channelId} />
        </TabsContent>

        <TabsContent value="sampling" className="mt-4">
          <SamplingWorkbench
            entityType="video"
            populationSize={countQuery.data?.count ?? 0}
            mutate={sampleMutation}
          />
        </TabsContent>

        <TabsContent value="folders" className="mt-4">
          <FoldersTab />
        </TabsContent>

        <TabsContent value="export" className="mt-4">
          <ExportTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
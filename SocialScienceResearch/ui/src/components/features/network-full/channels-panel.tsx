"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Search,
} from "lucide-react";
import { getChannels, getChannelVideos } from "@/services/api";
import type { Channel } from "@/services/api";
import type { Video } from "@/lib/types";
import { formatNumber } from "@/lib/format";
import {
  EmptyState,
  ErrorState,
  LoadingState,
} from "@/components/features/state";

function ChannelMeta({ channel }: { channel: Channel }) {
  const parts: string[] = [];
  if (channel.subscriber_count != null)
    parts.push(`${formatNumber(channel.subscriber_count)} subscribers`);
  if (channel.video_count != null)
    parts.push(`${formatNumber(channel.video_count)} videos`);
  if (channel.view_count != null)
    parts.push(`${formatNumber(channel.view_count)} views`);
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
      {channel.handle ? (
        <span className="font-mono">{channel.handle}</span>
      ) : null}
      {parts.map((p) => (
        <span key={p}>{p}</span>
      ))}
    </div>
  );
}

function ChannelVideos({ channelId }: { channelId: string }) {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["channel-videos", channelId],
    queryFn: () => getChannelVideos(channelId),
  });

  if (isLoading) return <LoadingState label="Loading videos…" />;
  if (isError)
    return (
      <ErrorState
        message={error instanceof Error ? error.message : "Failed to load videos"}
        retry={() => refetch()}
      />
    );
  const videos = data ?? [];
  if (videos.length === 0)
    return (
      <p className="px-1 py-2 text-xs text-muted-foreground">
        No videos recorded for this channel.
      </p>
    );
  return (
    <ul className="max-h-80 space-y-1 overflow-y-auto rounded-md border border-border bg-muted/30 p-2">
      {videos.map((video: Video) => (
        <li
          key={video.video_id}
          className="flex items-center gap-3 rounded px-1 py-1 hover:bg-muted"
        >
          {video.thumbnail_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={video.thumbnail_url}
              alt=""
              width={48}
              height={27}
              className="h-7 w-12 shrink-0 rounded object-cover"
            />
          ) : (
            <span className="h-7 w-12 shrink-0 rounded bg-muted" />
          )}
          <span className="min-w-0 flex-1 truncate text-sm">
            {video.title ?? video.video_id}
          </span>
          <Button
            variant="ghost"
            size="sm"
            nativeButton={false}
            render={<Link href={`/network/videos/${video.video_id}`} />}
          >
            <ExternalLink className="size-3" aria-hidden />
            Analytics
          </Button>
        </li>
      ))}
    </ul>
  );
}

export function ChannelsPanel() {
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["channels", debounced],
    queryFn: () => getChannels(undefined, debounced || undefined),
  });

  const channels = useMemo(() => data?.items ?? [], [data]);

  return (
    <div className="space-y-4" data-testid="channels-panel">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-sm">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search channels by name or handle…"
            className="pl-8"
            aria-label="Search channels"
          />
        </div>
        {channels.length ? (
          <Badge variant="outline">{formatNumber(channels.length)} channel(s)</Badge>
        ) : null}
      </div>

      {isLoading ? (
        <LoadingState label="Loading channels…" />
      ) : isError ? (
        <ErrorState
          message={error instanceof Error ? error.message : "Failed to load channels"}
          retry={() => refetch()}
        />
      ) : channels.length === 0 ? (
        <EmptyState
          title="No channels found"
          description={
            debounced
              ? `No channel matches “${debounced}”.`
              : "No channels have been collected yet."
          }
        />
      ) : (
        <div className="space-y-2">
          {channels.map((channel) => {
            const isOpen = expanded === channel.channel_id;
            return (
              <Card key={channel.channel_id} className="p-3">
                <button
                  type="button"
                  data-testid="channel-row"
                  className="flex w-full items-center gap-2 text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
                  aria-expanded={isOpen}
                  onClick={() =>
                    setExpanded(isOpen ? null : channel.channel_id)
                  }
                >
                  {isOpen ? (
                    <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
                  )}
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">
                      {channel.title ?? channel.channel_id}
                    </span>
                    <ChannelMeta channel={channel} />
                  </span>
                </button>
                {isOpen ? (
                  <div className="mt-3">
                    <ChannelVideos channelId={channel.channel_id} />
                  </div>
                ) : null}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ChevronRight } from "lucide-react";
import { ChannelLongitudinalChart } from "@/components/features/analytics/longitudinal-chart";
import { useChannels } from "@/services/queries";

export default function ChannelHistoryPage() {
  const params = useParams<{ channelId: string }>();
  const channelId = String(params.channelId ?? "");
  const channelsQuery = useChannels();
  const channelTitle =
    channelsQuery.data?.find((c) => c.channel_id === channelId)?.title ?? null;

  return (
    <div className="space-y-4">
      <nav
        aria-label="Breadcrumb"
        className="flex items-center gap-1 text-xs text-muted-foreground"
      >
        <Link href="/" className="underline-offset-2 hover:underline">
          Workspace
        </Link>
        <ChevronRight className="size-3" aria-hidden />
        <Link
          href={`/channels/${channelId}`}
          className="underline-offset-2 hover:underline"
        >
          {channelTitle ?? channelId}
        </Link>
        <ChevronRight className="size-3" aria-hidden />
        <span>History</span>
      </nav>

      <header className="flex flex-wrap items-center gap-2">
        <h1 className="text-lg font-semibold">{channelTitle ?? channelId}</h1>
        <code className="text-xs text-muted-foreground">history</code>
      </header>

      <ChannelLongitudinalChart channelId={channelId} />

      <p className="text-xs text-muted-foreground">
        Observation gaps greater than 30 days are flagged so you can see where
        readings are sparse. Every metric on this page comes from recorded
        observations — data is observed, never estimated.
      </p>
    </div>
  );
}
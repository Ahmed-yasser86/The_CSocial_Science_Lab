"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ChevronRight } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useVideo } from "@/services/queries";
import { VideoLongitudinalChart } from "@/components/features/analytics/longitudinal-chart";
import { CommentParticipation } from "@/components/features/analytics/comment-participation";
import { CommentReplies } from "@/components/features/analytics/comment-replies";
import { VelocityChart } from "@/components/features/analytics/velocity-chart";

type TabId = "longitudinal" | "comments";

export default function VideoHistoryPage() {
  const params = useParams<{ videoId: string }>();
  const videoId = String(params.videoId ?? "");
  const [tab, setTab] = useState<TabId>("longitudinal");
  const videoQuery = useVideo(videoId);

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
          href={`/videos/${videoId}`}
          className="underline-offset-2 hover:underline"
        >
          {videoQuery.data?.title ?? videoId}
        </Link>
        <ChevronRight className="size-3" aria-hidden />
        <span>History</span>
      </nav>

      <header className="flex flex-wrap items-center gap-2">
        <h1 className="text-lg font-semibold">
          {videoQuery.data?.title ?? videoId}
        </h1>
        <code className="text-xs text-muted-foreground">history</code>
      </header>

      <Tabs value={tab} onValueChange={(v) => setTab(v as TabId)} className="w-full">
        <TabsList>
          <TabsTrigger value="longitudinal">Longitudinal</TabsTrigger>
          <TabsTrigger value="comments">Comment analytics</TabsTrigger>
        </TabsList>

        <TabsContent value="longitudinal" className="mt-4">
          <VideoLongitudinalChart videoId={videoId} />
        </TabsContent>

        <TabsContent value="comments" className="mt-4">
          <div className="grid gap-4">
            <CommentParticipation videoId={videoId} />
            <CommentReplies videoId={videoId} />
            <VelocityChart videoId={videoId} />
          </div>
        </TabsContent>
      </Tabs>

      <p className="text-xs text-muted-foreground">
        Every metric on this page comes from recorded observations — data is
        observed, never estimated.
      </p>
    </div>
  );
}
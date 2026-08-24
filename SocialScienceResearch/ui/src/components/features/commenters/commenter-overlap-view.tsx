"use client";

import { useMemo, useState, type ReactNode } from "react";
import { useSearchParams } from "next/navigation";
import { Maximize2, Search, Sparkles } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState, ErrorState, LoadingState } from "@/components/features/state";
import { useChannels } from "@/services/queries";
import { useCommenterOverlap } from "@/services/commenters";
import { formatNumber } from "@/lib/format";
import type {
  CommenterOverlapResult,
  OverlapMetric,
} from "@/lib/commenter-overlap-types";
import { OverlapHeatmap } from "@/components/features/commenters/overlap-heatmap";
import { OverlapPairsTable } from "@/components/features/commenters/overlap-pairs-table";
import {
  BridgeCommentersPanel,
  TopSharedCommentersPanel,
} from "@/components/features/commenters/shared-commenters-panel";

type ProjectionKind = "videos" | "channels";

const METRIC_LABELS: Record<OverlapMetric, string> = {
  jaccard: "Jaccard",
  overlap_coefficient: "Overlap coefficient",
  intersection: "Intersection size",
};

function parseIds(input: string): string[] {
  return [...new Set(input.split(/[,\s\n]+/).map((s) => s.trim()).filter(Boolean))];
}

export function CommenterOverlapView({
  initialVideoIds = [],
  initialChannelIds = [],
}: {
  initialVideoIds?: string[];
  initialChannelIds?: string[];
}) {
  const searchParams = useSearchParams();
  const channelsQuery = useChannels();

  const [videoInput, setVideoInput] = useState(
    () => searchParams.get("video_ids") ?? initialVideoIds.join(","),
  );
  const [channelSel, setChannelSel] = useState<Set<string>>(
    () =>
      new Set([
        ...initialChannelIds,
        ...(searchParams.get("channel_ids") ?? "")
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      ]),
  );
  const [metric, setMetric] = useState<OverlapMetric>(
    () =>
      ((searchParams.get("metric") as OverlapMetric) in METRIC_LABELS
        ? (searchParams.get("metric") as OverlapMetric)
        : "jaccard"),
  );
  const [minEntities, setMinEntities] = useState(2);
  const [minShared, setMinShared] = useState(1);
  const [topN, setTopN] = useState(50);
  const [applied, setApplied] = useState<{
    videoIds: string[];
    channelIds: string[];
  } | null>(() => {
    const videos = parseIds(searchParams.get("video_ids") ?? initialVideoIds.join(","));
    const channels = [
      ...initialChannelIds,
      ...(searchParams.get("channel_ids") ?? "")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
    ];
    return videos.length || channels.length
      ? { videoIds: videos, channelIds: channels }
      : null;
  });

  const videoIds = useMemo(() => parseIds(videoInput), [videoInput]);
  const hasSelection = videoIds.length > 0 || channelSel.size > 0;

  const query = useCommenterOverlap(
    {
      videoIds: applied?.videoIds ?? [],
      channelIds: applied?.channelIds ?? [],
      metric,
      minEntities,
      minShared,
      topN,
    },
    { enabled: applied !== null },
  );

  const result: CommenterOverlapResult | undefined = query.data;
  const [projection, setProjection] = useState<ProjectionKind>("videos");

  function applyScope() {
    setApplied({
      videoIds,
      channelIds: [...channelSel],
    });
  }

  function toggleChannel(channelId: string) {
    setChannelSel((prev) => {
      const next = new Set(prev);
      if (next.has(channelId)) {
        next.delete(channelId);
      } else {
        next.add(channelId);
      }
      return next;
    });
  }

  return (
    <div className="space-y-6">
      <Card className="p-4">
        <div className="mb-3 flex items-center gap-2">
          <Sparkles className="size-4 text-muted-foreground" aria-hidden />
          <h3 className="text-sm font-medium">Scope</h3>
          <span className="text-xs text-muted-foreground">
            Pick videos and/or channels whose commenter sets should be compared.
          </span>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-2">
            <Label>Channels</Label>
            {channelsQuery.isLoading ? (
              <p className="text-xs text-muted-foreground">Loading channels…</p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {(channelsQuery.data ?? []).length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    No channels in the corpus.
                  </p>
                ) : (
                  (channelsQuery.data ?? []).map((channel) => (
                    <button
                      key={channel.channel_id}
                      type="button"
                      onClick={() => toggleChannel(channel.channel_id)}
                      aria-pressed={channelSel.has(channel.channel_id)}
                      className="rounded-full border border-border px-2.5 py-1 text-xs transition-colors hover:border-foreground/40 aria-pressed:border-foreground/60 aria-pressed:bg-muted"
                    >
                      {channel.title ?? channel.channel_id}
                    </button>
                  ))
                )}
              </div>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="video-ids">Video IDs (comma-separated)</Label>
            <Textarea
              id="video-ids"
              value={videoInput}
              onChange={(e) => setVideoInput(e.target.value)}
              placeholder="e.g. dQw4w9WgXcQ, 9bZkp7q19f0"
              rows={3}
              aria-label="Video IDs"
            />
          </div>
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <div className="space-y-2">
            <Label htmlFor="metric">Metric</Label>
            <Select value={metric} onValueChange={(v) => setMetric(v as OverlapMetric)}>
              <SelectTrigger id="metric" aria-label="Metric">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(METRIC_LABELS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="min-entities">Min entities</Label>
            <Input
              id="min-entities"
              type="number"
              min={1}
              value={minEntities}
              onChange={(e) => setMinEntities(Number(e.target.value) || 2)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="min-shared">Min shared</Label>
            <Input
              id="min-shared"
              type="number"
              min={1}
              value={minShared}
              onChange={(e) => setMinShared(Number(e.target.value) || 1)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="top-n">Top shared</Label>
            <Input
              id="top-n"
              type="number"
              min={1}
              value={topN}
              onChange={(e) => setTopN(Number(e.target.value) || 50)}
            />
          </div>
          <div className="flex items-end">
            <Button
              type="button"
              onClick={applyScope}
              disabled={!hasSelection}
              className="w-full"
            >
              <Search className="mr-2 size-4" aria-hidden />
              Analyze
            </Button>
          </div>
        </div>
      </Card>

      {applied === null ? (
        <EmptyState
          title="No scope selected"
          description="Choose at least one channel or video, then press Analyze."
        />
      ) : query.isLoading ? (
        <LoadingState label="Computing commenter overlap…" />
      ) : query.isError ? (
        <ErrorState
          message={query.error instanceof Error ? query.error.message : "Request failed"}
          retry={() => query.refetch()}
        />
      ) : result ? (
        <OverlapResults
          result={result}
          projection={projection}
          onProjectionChange={setProjection}
          metricLabel={METRIC_LABELS[metric]}
        />
      ) : null}
    </div>
  );
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <Card className="flex flex-col gap-1 p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="text-xl font-semibold tabular-nums">{value}</p>
    </Card>
  );
}

function ExpandableCard({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <>
      <Card className="relative">
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-sm">{title}</CardTitle>
          <Button
            variant="ghost"
            size="icon"
            aria-label={`Expand ${title}`}
            onClick={() => setExpanded(true)}
          >
            <Maximize2 className="size-4" aria-hidden />
          </Button>
        </CardHeader>
        <CardContent>{children}</CardContent>
      </Card>
      <Dialog
        open={expanded}
        onOpenChange={(open) => {
          if (!open) setExpanded(false);
        }}
      >
        <DialogContent className="fixed inset-0 top-0 left-0 z-50 flex h-screen w-screen max-h-none max-w-none translate-x-0 translate-y-0 flex-col overflow-hidden rounded-none p-0 sm:max-w-none">
          <DialogHeader className="border-b px-4 py-3">
            <DialogTitle>{title}</DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-auto p-4">{children}</div>
        </DialogContent>
      </Dialog>
    </>
  );
}

function OverlapResults({
  result,
  projection,
  onProjectionChange,
  metricLabel,
}: {
  result: CommenterOverlapResult;
  projection: ProjectionKind;
  onProjectionChange: (kind: ProjectionKind) => void;
  metricLabel: string;
}) {
  const projectionData = projection === "videos" ? result.videos : result.channels;
  const summary = projectionData?.summary;

  return (
    <div className="space-y-6" data-testid="commenter-overlap-results">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        <Tile
          label="Unique commenters"
          value={formatNumber(result.global_summary.unique_commenters)}
        />
        <Tile
          label="Comments in scope"
          value={formatNumber(result.global_summary.comment_count)}
        />
        <Tile
          label="Bridge commenters"
          value={formatNumber(result.global_summary.bridge_commenter_count)}
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-medium">
          Projection · {metricLabel}
        </h3>
        <Tabs
          value={projection}
          onValueChange={(v) => onProjectionChange(v as ProjectionKind)}
          className="ml-auto"
        >
          <TabsList aria-label="Projection level">
            <TabsTrigger value="videos">Videos</TabsTrigger>
            <TabsTrigger value="channels">Channels</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {projectionData && summary ? (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <Tile label="Entities" value={formatNumber(summary.entity_count)} />
            <Tile
              label="Commenters"
              value={formatNumber(summary.commenter_count)}
            />
            <Tile label="Comments" value={formatNumber(summary.comment_count)} />
            <Tile label="Pairs" value={formatNumber(summary.pair_count)} />
            <Tile
              label="Avg Jaccard"
              value={
                summary.average_jaccard === null ||
                summary.average_jaccard === undefined
                  ? "–"
                  : summary.average_jaccard.toFixed(3)
              }
            />
            <Tile
              label="Unidentified comments"
              value={formatNumber(summary.unidentified_comments)}
            />
            <Tile
              label="Max shared pair"
              value={
                summary.max_shared_pair
                  ? `${formatNumber(summary.max_shared_pair.intersection_size)}`
                  : "–"
              }
            />
            <Tile
              label="Bridges"
              value={formatNumber(summary.bridge_commenter_count)}
            />
          </div>

          {projectionData.entities.length < 2 ? (
            <EmptyState
              title="Not enough entities"
              description="At least two entities with commenters are required for overlap analysis."
            />
          ) : (
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <div className="space-y-4">
              <ExpandableCard title="Overlap heatmap">
                <OverlapHeatmap projection={projectionData} />
              </ExpandableCard>
              <ExpandableCard title="Top shared pairs">
                <OverlapPairsTable pairs={projectionData.pairs} />
              </ExpandableCard>
            </div>
            <div className="space-y-4">
              <ExpandableCard title="Bridge commenters">
                <BridgeCommentersPanel commenters={projectionData.bridge_commenters} />
              </ExpandableCard>
              <ExpandableCard title="Top shared commenters">
                <TopSharedCommentersPanel
                  commenters={projectionData.top_shared_commenters}
                />
              </ExpandableCard>
            </div>
          </div>
          )}
        </>
      ) : (
        <EmptyState
          title="No overlap computed"
          description="The selected scope produced no comparable commenter sets."
        />
      )}
    </div>
  );
}

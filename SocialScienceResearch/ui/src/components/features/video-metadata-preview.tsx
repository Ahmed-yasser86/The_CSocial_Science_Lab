"use client";

import { useState } from "react";
import { Video as VideoIcon, ExternalLink, ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useVideoPreview, useVideoEngagementPreview } from "@/hooks/useVideoPreview";
import { formatDate, formatDuration, formatNumber, formatDateTime } from "@/lib/format";
import type { Video } from "@/lib/types";

interface VideoMetadataPreviewProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  videoId: string;
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="py-3 border-b border-border/50 last:border-0">
      <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2">
        {title}
      </h4>
      <div className="space-y-1.5">{children}</div>
    </div>
  );
}

function Field({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={`text-sm text-right ${mono ? "font-mono tabular-nums" : ""}`}>
        {value}
      </span>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="flex items-center justify-center py-12">
      <Loader2 className="size-6 animate-spin text-muted-foreground" />
      <span className="ml-2 text-sm text-muted-foreground">Loading video metadata…</span>
    </div>
  );
}

function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
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

function VideoBasicSection({ video }: { video: Video }) {
  return (
    <Section title="Basic">
      <Field label="Title" value={video.title ?? "—"} />
      <Field
        label="Duration"
        value={
          video.duration !== null && video.duration !== undefined ? (
            formatDuration(video.duration)
          ) : (
            "—"
          )
        }
        mono
      />
      <Field
        label="Uploaded"
        value={
          video.upload_date ? formatDate(video.upload_date) : "—"
        }
      />
      <Field label="Channel" value={video.channel_id ?? "—"} mono />
      {video.language && <Field label="Language" value={video.language} />}
    </Section>
  );
}

function VideoContentSection({ video }: { video: Video }) {
  return (
    <Section title="Content">
      <div className="flex flex-wrap gap-1">
        {video.tags.length > 0 ? (
          video.tags.map((tag: string) => (
            <Badge key={tag} variant="outline" className="text-xs">
              {tag}
            </Badge>
          ))
        ) : (
          <span className="text-xs text-muted-foreground">No tags</span>
        )}
      </div>
      <div className="flex flex-wrap gap-1 mt-2">
        {video.categories.length > 0 ? (
          video.categories.map((cat: string) => (
            <Badge key={cat} variant="secondary" className="text-xs">
              {cat}
            </Badge>
          ))
        ) : (
          <span className="text-xs text-muted-foreground">No categories</span>
        )}
      </div>
    </Section>
  );
}

function VideoTechnicalSection({ video }: { video: Video }) {
  return (
    <Section title="Technical">
      <Field
        label="Type"
        value={
          video.is_short ? (
            <Badge variant="outline" className="text-xs">Short</Badge>
          ) : (
            <Badge variant="secondary" className="text-xs">Long</Badge>
          )
        }
      />
      <Field label="Live Status" value={video.live_status ?? "—"} />
      <Field label="Availability" value={video.availability ?? "—"} />
      <Field
        label="Age Limit"
        value={
          video.age_limit
            ? video.age_limit === 18
              ? "18+"
              : `${video.age_limit}+`
            : "—"
        }
      />
      {video.thumbnail_url && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Thumbnail</span>
          <a
            href={video.thumbnail_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-primary underline-offset-2 hover:underline flex items-center gap-1"
          >
            <ExternalLink className="size-3" />
            View
          </a>
        </div>
      )}
    </Section>
  );
}

function VideoStatsSection({
  videoId,
}: {
  videoId: string;
}) {
  const { data: engagement, isLoading, error, refetch } = useVideoEngagementPreview(videoId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <ErrorState
        message={error instanceof Error ? error.message : "Failed to load stats"}
        onRetry={() => refetch()}
      />
    );
  }

  if (!engagement) {
    return (
      <Section title="Stats">
        <p className="text-xs text-muted-foreground">No engagement data available</p>
      </Section>
    );
  }

  return (
    <Section title="Stats (Latest Observation)">
      <Field
        label="Views"
        value={
          engagement.views.availability === "available" ? (
            formatNumber(engagement.views.value)
          ) : (
            <span className="text-muted-foreground">{engagement.views.availability}</span>
          )
        }
        mono
      />
      <Field
        label="Likes"
        value={
          engagement.likes.availability === "available" ? (
            formatNumber(engagement.likes.value)
          ) : (
            <span className="text-muted-foreground">{engagement.likes.availability}</span>
          )
        }
        mono
      />
      <Field
        label="Comments"
        value={
          engagement.comments.availability === "available" ? (
            formatNumber(engagement.comments.value)
          ) : (
            <span className="text-muted-foreground">{engagement.comments.availability}</span>
          )
        }
        mono
      />
      {engagement.observed_at && (
        <Field
          label="Observed At"
          value={formatDateTime(engagement.observed_at)}
          mono
        />
      )}
    </Section>
  );
}

function RawJsonSection({ rawJson }: { rawJson: Record<string, unknown> }) {
  const [expanded, setExpanded] = useState(false);

  if (!rawJson || Object.keys(rawJson).length === 0) {
    return (
      <Section title="Raw JSON">
        <p className="text-xs text-muted-foreground">No raw JSON data available</p>
      </Section>
    );
  }

  return (
    <div className="py-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-xs font-medium uppercase tracking-wide text-muted-foreground hover:text-foreground transition-colors"
      >
        {expanded ? (
          <ChevronDown className="size-3.5" />
        ) : (
          <ChevronRight className="size-3.5" />
        )}
        Raw JSON ({Object.keys(rawJson).length} fields)
      </button>
      {expanded && (
        <pre className="mt-2 max-h-64 overflow-auto rounded-md border bg-muted/30 p-3 text-xs">
          {JSON.stringify(rawJson, null, 2)}
        </pre>
      )}
    </div>
  );
}

export function VideoMetadataPreview({
  open,
  onOpenChange,
  videoId,
}: VideoMetadataPreviewProps) {
  const { data: video, isLoading, error, refetch } = useVideoPreview(videoId);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <VideoIcon className="size-5" aria-hidden />
            Video Metadata
          </DialogTitle>
          <DialogDescription>
            {video
              ? video.title ?? videoId
              : "View full metadata for this video"}
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="flex-1 -mx-2 px-2">
          {isLoading && <LoadingState />}
          {error && (
            <ErrorState
              message={error instanceof Error ? error.message : "Failed to load video"}
              onRetry={() => refetch()}
            />
          )}
          {!isLoading && !error && !video && (
            <p className="text-sm text-muted-foreground text-center py-8">
              Video not found
            </p>
          )}
          {!isLoading && !error && video && (
            <Tabs defaultValue="overview">
              <TabsList>
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="raw">Raw JSON</TabsTrigger>
              </TabsList>
              <TabsContent value="overview" className="mt-4">
                <VideoBasicSection video={video} />
                <VideoStatsSection videoId={videoId} />
                <VideoContentSection video={video} />
                <VideoTechnicalSection video={video} />
              </TabsContent>
              <TabsContent value="raw">
                <RawJsonSection rawJson={video.raw_json} />
              </TabsContent>
            </Tabs>
          )}
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}

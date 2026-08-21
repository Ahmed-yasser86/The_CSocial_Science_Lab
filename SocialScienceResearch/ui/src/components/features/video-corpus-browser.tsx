"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Filter, X, Loader2, Play } from "lucide-react";
import type { Video, VideoFilter, CollectionSpec, CollectJobResult, Job } from "@/lib/types";
import {
  useChannelVideos,
  useChannelVideoCount,
  useSubmitCollect,
  useJob,
  useCancelJob,
} from "@/services/queries";
import { getJobResult } from "@/services/api";
import { DataTable, type Column } from "@/components/features/data-table";
import {
  LoadingState,
  ErrorState,
} from "@/components/features/state";
import { formatDate, formatDuration, formatNumber } from "@/lib/format";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Card } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

function parseFilter(searchParams: Record<string, string | string[] | undefined>): VideoFilter {
  const first = (key: string) => {
    const value = searchParams[key];
    return Array.isArray(value) ? value[0] : value;
  };
  const split = (key: string) =>
    first(key) ? first(key)!.split(",").filter(Boolean) : undefined;
  return {
    date_from: first("date_from") || undefined,
    date_to: first("date_to") || undefined,
    video_type: (first("video_type") as VideoFilter["video_type"]) || undefined,
    duration_min: first("duration_min") ? Number(first("duration_min")) : undefined,
    duration_max: first("duration_max") ? Number(first("duration_max")) : undefined,
    views_min: first("views_min") ? Number(first("views_min")) : undefined,
    views_max: first("views_max") ? Number(first("views_max")) : undefined,
    upload_hour: first("upload_hour") ? Number(first("upload_hour")) : undefined,
    upload_weekday: first("upload_weekday")
      ? Number(first("upload_weekday"))
      : undefined,
    keywords: split("keywords"),
    tags: split("tags"),
    category: first("category") || undefined,
  };
}

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function VideoCorpusBrowser({
  channelId,
  searchParams,
}: {
  channelId: string;
  searchParams: Record<string, string | string[] | undefined>;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const initial = useMemo(() => parseFilter(searchParams), [searchParams]);
  const [filter, setFilter] = useState<VideoFilter>(initial);

  const videosQuery = useChannelVideos(channelId, filter);
  const countQuery = useChannelVideoCount(channelId);
  const submit = useSubmitCollect();
  const cancel = useCancelJob();
  const [jobId, setJobId] = useState<string | null>(null);
  const [result, setResult] = useState<CollectJobResult | null>(null);
  const jobQuery = useJob(jobId);
  const job = jobQuery.data;

  const running = submit.isPending || job?.status === "pending" || job?.status === "running";
  const finished = job?.status === "succeeded" || job?.status === "failed" || job?.status === "cancelled";

  useEffect(() => {
    if (job?.status !== "succeeded" || result) return;
    getJobResult(job.job_id)
      .then(setResult)
      .catch(() => setResult(null));
  }, [job, result]);

  const filteredVideos = videosQuery.data ?? [];

  function collectFiltered() {
    if (filteredVideos.length === 0 || running) return;
    setResult(null);
    const spec: CollectionSpec = {
      targets: filteredVideos.map((v) => ({
        kind: "video",
        url: v.url || `https://www.youtube.com/watch?v=${v.video_id}`,
      })),
    };
    submit.mutate(spec, {
      onSuccess: (data) => setJobId(data.job_id),
    });
  }

  function cancelRun() {
    if (!jobId) return;
    cancel.mutate(jobId);
  }

  function apply(next: VideoFilter) {
    setFilter(next);
    const params = new URLSearchParams();
    if (next.date_from) params.set("date_from", next.date_from);
    if (next.date_to) params.set("date_to", next.date_to);
    if (next.video_type) params.set("video_type", next.video_type);
    if (next.duration_min !== undefined) params.set("duration_min", String(next.duration_min));
    if (next.duration_max !== undefined) params.set("duration_max", String(next.duration_max));
    if (next.views_min !== undefined) params.set("views_min", String(next.views_min));
    if (next.views_max !== undefined) params.set("views_max", String(next.views_max));
    if (next.upload_hour !== undefined) params.set("upload_hour", String(next.upload_hour));
    if (next.upload_weekday !== undefined) params.set("upload_weekday", String(next.upload_weekday));
    if (next.keywords?.length) params.set("keywords", next.keywords.join(","));
    if (next.tags?.length) params.set("tags", next.tags.join(","));
    if (next.category) params.set("category", next.category);
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname);
  }

  function reset() {
    setFilter({});
    router.replace(pathname);
  }

  const activeCount = countQuery.data?.count ?? 0;

  const columns: Column<Video>[] = [
    {
      key: "title",
      header: "Title",
      sortable: true,
      sortValue: (v) => v.title ?? "",
      cell: (v) => (
        <Link
          href={`/videos/${v.video_id}`}
          className="line-clamp-2 max-w-md text-sm text-primary underline-offset-2 hover:underline"
        >
          {v.title ?? v.video_id}
        </Link>
      ),
    },
    {
      key: "video_id",
      header: "Video id",
      sortable: true,
      sortValue: (v) => v.video_id,
      cell: (v) => <code className="text-xs text-muted-foreground">{v.video_id}</code>,
    },
    {
      key: "upload_date",
      header: "Published",
      sortable: true,
      sortValue: (v) => v.upload_date ?? "",
      cell: (v) => formatDate(v.upload_date),
    },
    {
      key: "duration",
      header: "Duration",
      sortable: true,
      sortValue: (v) => v.duration,
      cell: (v) => formatDuration(v.duration),
    },
    {
      key: "is_short",
      header: "Format",
      sortable: true,
      sortValue: (v) => (v.is_short === true ? "short" : v.live_status ?? "long"),
      cell: (v) => (
        <Badge variant="outline">
          {v.is_short === true
            ? "short"
            : v.live_status === "is_live" || v.live_status === "was_live"
              ? "live"
              : "long"}
        </Badge>
      ),
    },
    {
      key: "tags",
      header: "Tags",
      cell: (v) => (
        <div className="flex max-w-xs flex-wrap gap-1">
          {(v.tags ?? []).slice(0, 4).map((tag) => (
            <code key={tag} className="text-[10px] text-muted-foreground">
              {tag}
            </code>
          ))}
          {(v.tags ?? []).length > 4 ? (
            <span className="text-[10px] text-muted-foreground">
              +{(v.tags ?? []).length - 4}
            </span>
          ) : null}
        </div>
      ),
    },
    {
      key: "comment_count",
      header: "Comments",
      sortable: true,
      sortValue: (v) => v.comment_count ?? -1,
      cell: (v) => (
        <Link
          href={`/videos/${v.video_id}?tab=comments`}
          className="font-mono tabular-nums text-primary underline-offset-2 hover:underline"
        >
          {v.comment_count !== null && v.comment_count !== undefined
            ? formatNumber(v.comment_count)
            : "—"}
        </Link>
      ),
    },
  ];

  return (
    <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
      <aside aria-label="Corpus filters">
        <div className="sticky top-20 space-y-3 rounded-md border p-3">
          <div className="flex items-center justify-between">
            <h2 className="flex items-center gap-1.5 text-sm font-medium">
              <Filter className="size-4 text-muted-foreground" aria-hidden />
              Filters
            </h2>
            <Button variant="ghost" size="sm" onClick={reset}>
              <X className="size-3.5" aria-hidden />
              Reset
            </Button>
          </div>

          <Field label="Published from">
            <Input
              type="date"
              value={filter.date_from ?? ""}
              onChange={(e) =>
                setFilter({ ...filter, date_from: e.target.value || undefined })
              }
              onBlur={() => apply(filter)}
            />
          </Field>
          <Field label="Published to">
            <Input
              type="date"
              value={filter.date_to ?? ""}
              onChange={(e) =>
                setFilter({ ...filter, date_to: e.target.value || undefined })
              }
              onBlur={() => apply(filter)}
            />
          </Field>
          <Field label="Format">
            <Select
              value={filter.video_type ?? "any"}
              onValueChange={(v) =>
                apply({ ...filter, video_type: v === "any" ? undefined : (v as VideoFilter["video_type"]) })
              }
              items={[
                { value: "any", label: "Any" },
                { value: "short", label: "Short" },
                { value: "long", label: "Long (≥5m)" },
                { value: "live", label: "Live" },
              ]}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="w-[--anchor-width]">
                {["any", "short", "long", "live"].map((v) => (
                  <SelectItem key={v} value={v}>
                    {v === "any" ? "Any" : v === "short" ? "Short" : v === "long" ? "Long (≥5m)" : "Live"}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Duration min (s)">
              <Input
                type="number"
                min={0}
                value={filter.duration_min ?? ""}
                onChange={(e) =>
                  setFilter({ ...filter, duration_min: e.target.value ? Number(e.target.value) : undefined })
                }
                onBlur={() => apply(filter)}
              />
            </Field>
            <Field label="Duration max (s)">
              <Input
                type="number"
                min={0}
                value={filter.duration_max ?? ""}
                onChange={(e) =>
                  setFilter({ ...filter, duration_max: e.target.value ? Number(e.target.value) : undefined })
                }
                onBlur={() => apply(filter)}
              />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Views min">
              <Input
                type="number"
                min={0}
                value={filter.views_min ?? ""}
                onChange={(e) =>
                  setFilter({ ...filter, views_min: e.target.value ? Number(e.target.value) : undefined })
                }
                onBlur={() => apply(filter)}
              />
            </Field>
            <Field label="Views max">
              <Input
                type="number"
                min={0}
                value={filter.views_max ?? ""}
                onChange={(e) =>
                  setFilter({ ...filter, views_max: e.target.value ? Number(e.target.value) : undefined })
                }
                onBlur={() => apply(filter)}
              />
            </Field>
          </div>
          <Field label="Upload weekday">
            <Select
              value={filter.upload_weekday !== undefined ? String(filter.upload_weekday) : "any"}
              onValueChange={(v) =>
                apply({
                  ...filter,
                  upload_weekday: v === "any" ? undefined : Number(v),
                })
              }
              items={[
                { value: "any", label: "Any" },
                ...WEEKDAYS.map((day, i) => ({ value: String(i), label: day })),
              ]}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="w-[--anchor-width]">
                {["any", ...WEEKDAYS.map((_, i) => String(i))].map((v) => (
                  <SelectItem key={v} value={v}>
                    {v === "any" ? "Any" : WEEKDAYS[Number(v)]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field label="Keywords (comma-separated)">
            <Input
              value={(filter.keywords ?? []).join(",")}
              onChange={(e) =>
                setFilter({
                  ...filter,
                  keywords: e.target.value.split(",").map((k) => k.trim()).filter(Boolean),
                })
              }
              onBlur={() => apply(filter)}
            />
          </Field>
          <Field label="Tags (comma-separated)">
            <Input
              value={(filter.tags ?? []).join(",")}
              onChange={(e) =>
                setFilter({
                  ...filter,
                  tags: e.target.value.split(",").map((k) => k.trim()).filter(Boolean),
                })
              }
              onBlur={() => apply(filter)}
            />
          </Field>

          <p className="text-[11px] leading-relaxed text-muted-foreground">
            View-based filters apply to each video&apos;s latest observation.
            Videos without an observation are excluded, never estimated.
          </p>
        </div>
      </aside>

      <section aria-label="Video corpus">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-medium">Corpus</h2>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-xs text-muted-foreground">
              {countQuery.isSuccess ? formatNumber(activeCount) : "…"} video(s)
              in channel · {videosQuery.isSuccess ? formatNumber(filteredVideos.length) : "…"} matching
            </p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={collectFiltered}
              disabled={running || filteredVideos.length === 0}
              title={
                filteredVideos.length > 0
                  ? `Collect observations for the ${filteredVideos.length} video(s) currently matching the filters`
                  : "No videos match the current filters"
              }
            >
              {running ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden />
              ) : (
                <Play className="size-3.5" aria-hidden />
              )}
              Collect observations
            </Button>
          </div>
        </div>

        {running ? <CollectProgressCard job={job} onCancel={cancelRun} cancelling={cancel.isPending} /> : null}

        {finished && result ? <CollectResultSummary result={result} /> : null}

        {videosQuery.isLoading ? (
          <LoadingState label="Loading corpus…" />
        ) : videosQuery.isError ? (
          <ErrorState message={(videosQuery.error as Error).message} retry={() => videosQuery.refetch()} />
        ) : (
          <DataTable
            columns={columns}
            rows={videosQuery.data ?? []}
            getRowKey={(v) => v.video_id}
            initialSortKey="upload_date"
            initialSortDirection="desc"
            emptyTitle="No videos match these filters"
            emptyDescription="Adjust or reset the filters, or collect the channel to grow the corpus."
            ariaLabel="Channel video corpus"
          />
        )}
      </section>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      {children}
    </div>
  );
}

function CollectProgressCard({
  job,
  onCancel,
  cancelling,
}: {
  job: Job | undefined;
  onCancel: () => void;
  cancelling: boolean;
}) {
  const progress = job?.progress;
  const succeeded = progress?.succeeded ?? 0;
  const failed = progress?.failed ?? 0;
  const discovered = progress?.discovered ?? 0;
  const pct = discovered > 0 ? Math.round(((succeeded + failed) / discovered) * 100) : 0;

  return (
    <Card className="space-y-3 p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm">
          <Loader2 className="size-4 animate-spin text-muted-foreground" aria-hidden />
          <span className="font-medium capitalize">{progress?.stage ?? "running"}</span>
          <span className="font-mono text-xs text-muted-foreground">{job?.job_id}</span>
        </div>
        <Button variant="outline" size="sm" onClick={onCancel} disabled={cancelling}>
          Cancel
        </Button>
      </div>
      {discovered > 0 ? (
        <div className="space-y-1">
          <Progress value={pct} />
          <p className="text-xs text-muted-foreground">
            {formatNumber(succeeded)} succeeded, {formatNumber(failed)} failed of{" "}
            {formatNumber(discovered)} discovered
          </p>
        </div>
      ) : null}
      {progress?.message ? (
        <p className="text-xs text-muted-foreground">{progress.message}</p>
      ) : null}
    </Card>
  );
}

function CollectResultSummary({ result }: { result: CollectJobResult }) {
  const succeeded = result.results.filter((r) => r.status === "success" || r.status === "partial");
  const comments = result.results.reduce((sum, r) => sum + (r.comments_collected ?? 0), 0);
  return (
    <Card className="space-y-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm">
          <Play className="size-4 text-emerald-500" aria-hidden />
          <span className="font-medium">
            {formatNumber(succeeded.length)} of {formatNumber(result.results.length)} video(s) collected
          </span>
        </div>
        <Button
          render={<Link href="/runs" />}
          nativeButton={false}
          variant="outline"
          size="sm"
        >
          View runs
        </Button>
      </div>
      {comments > 0 ? (
        <p className="text-xs text-muted-foreground">
          {formatNumber(comments)} comment(s) collected in total.
        </p>
      ) : (
        <p className="text-xs text-muted-foreground">
          No comments were collected. Observations for views/likes are still recorded per video.
        </p>
      )}
      {result.results.some((r) => r.errors.length > 0) ? (
        <p className="text-xs text-destructive">
          {formatNumber(result.results.reduce((sum, r) => sum + r.errors.length, 0))} error(s)
          recorded across the run(s).
        </p>
      ) : null}
    </Card>
  );
}

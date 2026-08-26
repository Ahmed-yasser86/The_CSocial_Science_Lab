"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowLeft, ExternalLink, FlaskConical, Tag, XCircle } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { RunStatusBadge } from "@/components/features/run-status-badge";
import { LoadingState } from "@/components/features/state";
import { useCancelJob, useJob } from "@/services/queries";
import { setJobTags, setRunTags } from "@/services/api";
import { echoChamberKeys, listEchoDetections } from "@/services/echoChamber";
import type { JobRunSummary } from "@/lib/types";
import { formatDateTime } from "@/lib/format";

function TagEditor({
  tags,
  onSave,
}: {
  tags: string[];
  onSave: (tags: string[]) => Promise<unknown>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const save = useMutation({ mutationFn: onSave });

  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => {
          setDraft(tags.join(", "));
          setEditing(true);
        }}
        className="inline-flex items-center gap-1.5 rounded border px-2 py-1 text-xs text-muted-foreground hover:bg-muted"
        data-testid="tag-edit"
      >
        <Tag className="size-3" />
        {tags.length ? tags.join(", ") : "Add tags"}
      </button>
    );
  }
  return (
    <form
      className="flex items-center gap-1.5"
      onSubmit={(e) => {
        e.preventDefault();
        const next = draft
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean);
        void save.mutateAsync(next).then(() => setEditing(false));
      }}
    >
      <Input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        placeholder="tag1, tag2"
        className="h-7 w-48 text-xs"
        autoFocus
        data-testid="tag-input"
      />
      <Button type="submit" size="xs" disabled={save.isPending}>
        Save
      </Button>
    </form>
  );
}

function elapsed(started: string | null, finished: string | null): string {
  if (!started) return "—";
  const end = finished ? Date.parse(finished) : Date.now();
  const secs = Math.max(0, Math.round((end - Date.parse(started)) / 1000));
  if (secs < 60) return `${secs}s`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ${secs % 60}s`;
  return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`;
}

function RunCard({
  run,
  tags,
  onTag,
}: {
  run: JobRunSummary;
  tags: string[];
  onTag: (runId: string) => void;
}) {
  const discovered = Math.max(run.entities_discovered, run.entities_succeeded, 1);
  const succeededPct = Math.min(100, Math.round((run.entities_succeeded / discovered) * 100));
  const failedPct = Math.min(
    100 - succeededPct,
    Math.round((run.entities_failed / discovered) * 100),
  );
  const isTerminal = !["pending", "running"].includes(run.status);

  return (
    <Card className="p-4" data-testid="job-run-card">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-muted-foreground">{run.run_id}</span>
            <RunStatusBadge status={run.status} />
            {run.layer_index != null && (
              <span className="rounded bg-muted px-1.5 py-0.5 text-[10px]">
                layer {run.layer_index}
              </span>
            )}
          </div>
          <p className="mt-1 truncate text-sm">{run.name ?? run.target_url ?? "—"}</p>
          <p className="text-xs text-muted-foreground">
            started {formatDateTime(run.started_at)} · {elapsed(run.started_at, run.finished_at)}
          </p>
        </div>
        {run.target_video_id && (
          <Link
            href={`/videos/${run.target_video_id}`}
            className="shrink-0 text-muted-foreground hover:text-foreground"
            aria-label="Open video page"
          >
            <ExternalLink className="size-4" />
          </Link>
        )}
      </div>
      <div className="mt-3">
        <div
          className="flex h-2 w-full overflow-hidden rounded-full bg-muted"
          role="img"
          aria-label={`${run.entities_succeeded}/${discovered} succeeded`}
        >
          <div className="bg-emerald-500" style={{ width: `${succeededPct}%` }} />
          <div className="bg-red-400" style={{ width: `${failedPct}%` }} />
        </div>
        <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-muted-foreground">
          <span>{run.entities_succeeded}/{run.entities_discovered} succeeded</span>
          {run.entities_failed > 0 && (
            <span className="text-destructive">{run.entities_failed} failed</span>
          )}
          {run.comments_collected != null && run.comments_collected > 0 && (
            <span>{run.comments_collected} comments</span>
          )}
          {tags.length > 0 && (
            <span className="inline-flex items-center gap-1">
              <Tag className="size-3" />
              {tags.join(", ")}
            </span>
          )}
          {isTerminal && (
            <button
              type="button"
              className="ml-auto inline-flex items-center gap-1 underline-offset-2 hover:underline"
              onClick={() => onTag(run.run_id)}
              data-testid={`run-tag-${run.run_id}`}
            >
              <Tag className="size-3" /> tag
            </button>
          )}
          {!isTerminal && <span className="animate-pulse">working…</span>}
        </div>
      </div>
    </Card>
  );
}

function JobStatTile({
  label,
  value,
  className,
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div
      className="rounded-md border bg-muted/40 px-3 py-2"
      data-testid={`job-stat-${label.toLowerCase().replace(/[^a-z]+/g, "-")}`}
    >
      <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className={`text-lg font-semibold tabular-nums ${className ?? ""}`}>
        {value}
      </p>
    </div>
  );
}

export function JobDetailPage({ jobId }: { jobId: string }) {
  const jobQuery = useJob(jobId);
  const cancel = useCancelJob();
  const queryClient = useQueryClient();
  const job = jobQuery.data;
  const isActive = job ? ["pending", "running"].includes(job.status) : false;

  // Echo-chamber linkage: find the analysis this job belongs to so the
  // researcher can jump from provenance to the verdict it produced.
  const isEchoJob = job?.kind === "echo_chamber";
  const echoListQuery = useQuery({
    queryKey: echoChamberKeys.list,
    queryFn: () => listEchoDetections(),
    enabled: isEchoJob,
  });
  const linkedDetection =
    isEchoJob && echoListQuery.data
      ? echoListQuery.data.items.find((d) => d.job_id === jobId)
      : undefined;

  const saveTags = useMutation({
    mutationFn: (tags: string[]) => setJobTags(jobId, tags),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
      void queryClient.invalidateQueries({
        queryKey: ["jobs", "single", jobId],
      });
      void jobQuery.refetch();
    },
  });

  const saveRunTags = useMutation({
    mutationFn: ({ runId, tags }: { runId: string; tags: string[] }) =>
      setRunTags(runId, tags),
    onSuccess: () => jobQuery.refetch(),
  });

  if (jobQuery.isLoading) {
    return <LoadingState label="Loading job…" />;
  }

  if (jobQuery.isError || !job) {
    return (
      <Card className="p-6 text-sm text-destructive" data-testid="job-not-found">
        Job <code className="font-mono">{jobId}</code> was not found in this
        workspace. It may belong to another workspace or predate job
        persistence.
      </Card>
    );
  }

  const runs = [...(job.runs ?? [])].sort((a, b) =>
    (a.started_at ?? "").localeCompare(b.started_at ?? ""),
  );
  const totals = runs.reduce(
    (acc, r) => ({
      discovered: acc.discovered + Math.max(r.entities_discovered, 0),
      succeeded: acc.succeeded + Math.max(r.entities_succeeded, 0),
      failed: acc.failed + Math.max(r.entities_failed, 0),
      comments: acc.comments + Math.max(r.comments_collected ?? 0, 0),
    }),
    { discovered: 0, succeeded: 0, failed: 0, comments: 0 },
  );

  return (
    <div className="space-y-6" data-testid="job-detail-page">
      <div className="flex items-center justify-between gap-3">
        <Link
          href="/runs"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> All activity
        </Link>
        {isActive && (
          <Button
            variant="outline"
            size="sm"
            disabled={cancel.isPending || job.cancel_requested}
            onClick={() => cancel.mutate(job.job_id)}
            data-testid="job-detail-cancel"
          >
            <XCircle className="size-4" />
            {job.cancel_requested ? "Cancelling…" : "Cancel job"}
          </Button>
        )}
      </div>

      <Card className="p-5" data-testid="job-header">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="font-mono text-lg font-semibold">{job.job_id}</h1>
          <RunStatusBadge status={job.status} />
          <span className="rounded bg-muted px-1.5 py-0.5 text-xs uppercase tracking-wide text-muted-foreground">
            {job.kind}
          </span>
          {job.cancel_requested && isActive && (
            <span className="text-xs text-amber-600">cancellation requested…</span>
          )}
        </div>
        {job.message && <p className="mt-1 text-sm">{job.message}</p>}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <TagEditor
            tags={job.tags ?? []}
            onSave={(tags) => saveTags.mutateAsync(tags)}
          />
          {linkedDetection && (
            <p className="text-sm">
              <FlaskConical className="mr-1 inline size-4 text-muted-foreground" />
              Echo-chamber analysis{" "}
              <Link
                href="/network/echo-chambers"
                className="font-medium underline underline-offset-2"
                data-testid="job-echo-link"
              >
                {linkedDetection.detection_id}
              </Link>
            </p>
          )}
        </div>
        <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-sm text-muted-foreground sm:grid-cols-4">
          <div><dt className="inline">Created </dt><dd className="inline">{formatDateTime(job.created_at)}</dd></div>
          <div><dt className="inline">Started </dt><dd className="inline">{formatDateTime(job.started_at)}</dd></div>
          <div><dt className="inline">Finished </dt><dd className="inline">{formatDateTime(job.finished_at)}</dd></div>
          <div><dt className="inline">Elapsed </dt><dd className="inline">{elapsed(job.started_at, job.finished_at)}</dd></div>
        </dl>
        {runs.length > 0 && (
          <div
            className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6"
            data-testid="job-stats-tiles"
          >
            <JobStatTile label="Total runs" value={String(runs.length)} />
            <JobStatTile
              label="Discovered"
              value={totals.discovered.toLocaleString()}
            />
            <JobStatTile
              label="Succeeded"
              value={totals.succeeded.toLocaleString()}
              className="text-emerald-600"
            />
            <JobStatTile
              label="Failed"
              value={totals.failed.toLocaleString()}
              className={totals.failed > 0 ? "text-destructive" : undefined}
            />
            <JobStatTile
              label="Comments"
              value={totals.comments.toLocaleString()}
            />
            <JobStatTile
              label="Elapsed (latest run)"
              value={elapsed(job.started_at, job.finished_at)}
            />
          </div>
        )}
      </Card>

      {runs.length === 0 ? (
        <Card className="p-6 text-sm text-muted-foreground" data-testid="job-runs-empty">
          No child runs recorded yet. They appear here as soon as the worker
          starts scraping.
        </Card>
      ) : (
        <div className="space-y-3">
          <h2 className="text-sm font-medium text-muted-foreground">
            Runs under this job ({runs.length})
          </h2>
          {runs.map((run) => (
            <RunCard key={run.run_id} run={run} tags={run.tags ?? []} onTag={(runId) => { const input = window.prompt("Tags (comma-separated):", ""); if (input === null) return; void saveRunTags.mutateAsync({ runId, tags: input.split(",").map((t) => t.trim()).filter(Boolean), }); }} />
          ))}
        </div>
      )}
    </div>
  );
}

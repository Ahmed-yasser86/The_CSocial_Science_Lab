"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Loader2,
  ArrowRight,
  CircleAlert,
  Ban,
  CheckCircle2,
  Video,
  Film,
  Tv,
  Mic2,
  Layers,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card } from "@/components/ui/card";
import type { CollectionSpec, CollectionTargetKind, QueryGroup } from "@/lib/types";
import { CriteriaFilterBar } from "@/components/features/criteria-filter-bar";
import {
  useSubmitCollect,
  useJob,
  useCancelJob,
  useRuns,
} from "@/services/queries";
import { getJobResult } from "@/services/api";
import type { CollectJobResult } from "@/lib/types";
import { RunStatusBadge } from "@/components/features/run-status-badge";
import { ErrorList } from "@/components/features/error-list";
import { formatNumber } from "@/lib/format";

const EXAMPLES: Record<CollectionTargetKind, string> = {
  channel: "https://www.youtube.com/@channel",
  video: "https://www.youtube.com/watch?v=VIDEO_ID",
  recommendation: "https://www.youtube.com/watch?v=VIDEO_ID",
};

const KIND_TABS: { value: CollectionTargetKind; label: string }[] = [
  { value: "channel", label: "Channel" },
  { value: "video", label: "Video" },
  { value: "recommendation", label: "Recommendations" },
];

const VIDEO_TABS: { value: string; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { value: "videos", label: "Videos", icon: Video },
  { value: "shorts", label: "Shorts", icon: Film },
  { value: "streams", label: "Streams", icon: Tv },
  { value: "podcasts", label: "Podcasts", icon: Mic2 },
  { value: "stacks", label: "Stacks", icon: Layers },
];

export function CollectTargetForm({
  initialKind = "channel",
}: {
  initialKind?: CollectionTargetKind;
}) {
  const [kind, setKind] = useState<CollectionTargetKind>(initialKind);
  const [url, setUrl] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [collectComments, setCollectComments] = useState<boolean | null>(null);
  const [collectTranscripts, setCollectTranscripts] = useState(false);
  const [commentMinLikes, setCommentMinLikes] = useState("");
  const [commentDateFrom, setCommentDateFrom] = useState("");
  const [commentDateTo, setCommentDateTo] = useState("");
  const [maxComments, setMaxComments] = useState("");
  const [scrapeAllComments, setScrapeAllComments] = useState(false);
  const [maxVideosToEnrich, setMaxVideosToEnrich] = useState("");
  const [maxVideosPerChannel, setMaxVideosPerChannel] = useState("");
  const [includeLiveVideos, setIncludeLiveVideos] = useState(false);
  const [scrapeLiveOnly, setScrapeLiveOnly] = useState(false);
  const [videoTabs, setVideoTabs] = useState<string[]>([]);
  const [videoCriteria, setVideoCriteria] = useState<QueryGroup | null>(null);
  const [commentCriteria, setCommentCriteria] = useState<QueryGroup | null>(null);

  const [jobId, setJobId] = useState<string | null>(null);
  const [result, setResult] = useState<CollectJobResult | null>(null);

  const submit = useSubmitCollect();
  const jobQuery = useJob(jobId);
  const cancel = useCancelJob();

  const job = jobQuery.data;
  const running = submit.isPending || job?.status === "pending" || job?.status === "running";
  const finished = job?.status === "succeeded" || job?.status === "failed" || job?.status === "cancelled";

  // When the job reaches a terminal state, load its result once.
  useEffect(() => {
    if (job?.status !== "succeeded" || result) return;
    getJobResult(job.job_id)
      .then(setResult)
      .catch(() => setResult(null));
  }, [job, result]);

  function buildSpec(): CollectionSpec {
    const target: CollectionSpec = {
      targets: [{ kind, url: url.trim() }],
      collect_transcripts: collectTranscripts,
    };
    if (collectComments !== null) target.collect_comments = collectComments;
    const minLikes = parseInt(commentMinLikes, 10);
    if (!Number.isNaN(minLikes) && minLikes >= 0) target.comment_min_likes = minLikes;
    if (commentDateFrom) target.comment_date_from = new Date(commentDateFrom).toISOString();
    if (commentDateTo) target.comment_date_to = new Date(commentDateTo).toISOString();
    const cap = parseInt(maxComments, 10);
    if (!Number.isNaN(cap) && cap > 0) target.max_comments_per_video = cap;
    if (scrapeAllComments) target.scrape_all_comments = true;
    const enrich = parseInt(maxVideosToEnrich, 10);
    if (!Number.isNaN(enrich) && enrich > 0) target.max_videos_to_enrich = enrich;
    const perChannel = parseInt(maxVideosPerChannel, 10);
    if (!Number.isNaN(perChannel) && perChannel > 0) {
      target.max_videos_per_channel = perChannel;
    }
    if (includeLiveVideos) {
      target.include_live_videos = true;
    }
    if (scrapeLiveOnly) {
      target.scrape_live_only = true;
    }
    if (videoTabs.length > 0) {
      target.video_tabs = videoTabs;
    }
    if (videoCriteria && videoCriteria.conditions.length > 0) {
      target.video_criteria = videoCriteria;
    }
    if (commentCriteria && commentCriteria.conditions.length > 0) {
      target.comment_criteria = commentCriteria;
    }
    return target;
  }

  function submitForm(event: React.FormEvent) {
    event.preventDefault();
    if (!url.trim() || running) return;
    setResult(null);
    submit.mutate(buildSpec(), {
      onSuccess: (data) => setJobId(data.job_id),
    });
  }

  function cancelRun() {
    if (!jobId) return;
    cancel.mutate(jobId);
  }

  return (
    <div className="space-y-4">
      <form onSubmit={submitForm} className="space-y-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1 space-y-1.5">
            <label
              htmlFor="target-url"
              className="text-xs font-medium uppercase tracking-wide text-muted-foreground"
            >
              YouTube URL
            </label>
            <Input
              id="target-url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder={EXAMPLES[kind]}
              disabled={running}
              autoComplete="off"
              spellCheck={false}
              required
            />
          </div>
          <Button type="submit" disabled={running || !url.trim()}>
            {running ? (
              <>
                <Loader2 className="size-4 animate-spin" aria-hidden />
                Collecting…
              </>
            ) : (
              <>
                Start collection
                <ArrowRight className="size-4" aria-hidden />
              </>
            )}
          </Button>
        </div>

        <Tabs
          value={kind}
          onValueChange={(value) => setKind(value as CollectionTargetKind)}
          className="w-fit"
        >
          <TabsList>
            {KIND_TABS.map((tab) => (
              <TabsTrigger key={tab.value} value={tab.value}>
                {tab.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        {kind === "recommendation" ? (
          <p className="text-xs text-muted-foreground">
            Observes the video’s “Up Next” rail through a layered provider
            strategy and ranks each edge by its feed position.
          </p>
        ) : null}

        <div className="flex items-center gap-2 pt-1">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setShowAdvanced((v) => !v)}
          >
            {showAdvanced ? "Hide" : "Show"} researcher options
          </Button>
        </div>

        {showAdvanced ? (
          <>
            <div className="grid gap-4 rounded-md border p-4 sm:grid-cols-2">
            <div className="flex items-center gap-2">
              <Checkbox
                id="opt-comments"
                checked={collectComments ?? true}
                onCheckedChange={(v) => setCollectComments(v === true ? null : false)}
              />
              <Label htmlFor="opt-comments">Collect comments</Label>
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                id="opt-transcripts"
                checked={collectTranscripts}
                onCheckedChange={(v) => setCollectTranscripts(v === true)}
              />
              <Label htmlFor="opt-transcripts">
                Collect transcripts (external .txt artifacts)
              </Label>
            </div>
            <Field label="Minimum comment likes">
              <Input
                type="number"
                min={0}
                value={commentMinLikes}
                onChange={(e) => setCommentMinLikes(e.target.value)}
                placeholder="e.g. 10"
              />
            </Field>
            <Field label="Comments from">
              <Input
                type="date"
                value={commentDateFrom}
                onChange={(e) => setCommentDateFrom(e.target.value)}
              />
            </Field>
            <Field label="Comments until">
              <Input
                type="date"
                value={commentDateTo}
                onChange={(e) => setCommentDateTo(e.target.value)}
              />
            </Field>
            <Field label="Max comments per video">
              <Input
                type="number"
                min={1}
                value={maxComments}
                onChange={(e) => setMaxComments(e.target.value)}
                placeholder="unlimited"
                disabled={scrapeAllComments}
              />
            </Field>
            <div className="flex items-center gap-2">
              <Checkbox
                id="scrape-all-comments"
                checked={scrapeAllComments}
                onCheckedChange={(v) => {
                  setScrapeAllComments(v === true);
                  if (v === true) setMaxComments("");
                }}
              />
              <Label htmlFor="scrape-all-comments">Scrape all comments (no cap)</Label>
            </div>
            <Field label="Max videos to deep-enrich">
              <Input
                type="number"
                min={1}
                value={maxVideosToEnrich}
                onChange={(e) => setMaxVideosToEnrich(e.target.value)}
                placeholder="all"
              />
            </Field>
            <Field label="Max videos per channel">
              <Input
                type="number"
                min={1}
                value={maxVideosPerChannel}
                onChange={(e) => setMaxVideosPerChannel(e.target.value)}
                placeholder="all"
              />
            </Field>
            <div className="flex items-center gap-2">
              <Checkbox
                id="include-live-videos"
                checked={includeLiveVideos}
                onCheckedChange={(v) => setIncludeLiveVideos(v === true)}
              />
              <Label htmlFor="include-live-videos">Include live videos / streams</Label>
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                id="scrape-live-only"
                checked={scrapeLiveOnly}
                onCheckedChange={(v) => setScrapeLiveOnly(v === true)}
              />
              <Label htmlFor="scrape-live-only">Scrape live videos only</Label>
            </div>
          </div>

          {kind === "channel" && (
            <section className="space-y-2 rounded-md border p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Video tabs to collect
              </p>
              <div className="flex flex-wrap gap-3 mt-2">
                {VIDEO_TABS.map((tab) => (
                  <div key={tab.value} className="flex items-center gap-2">
                    <Checkbox
                      id={`video-tab-${tab.value}`}
                      checked={videoTabs.includes(tab.value)}
                      onCheckedChange={(checked) =>
                        setVideoTabs((prev) =>
                          checked
                            ? [...prev, tab.value]
                            : prev.filter((t) => t !== tab.value)
                        )
                      }
                    />
                    <Label htmlFor={`video-tab-${tab.value}`} className="flex items-center gap-1 cursor-pointer">
                      <tab.icon className="size-3.5" aria-hidden />
                      {tab.label}
                    </Label>
                  </div>
                ))}
              </div>
            </section>
          )}

          {kind === "channel" ? (
            <section className="space-y-2 rounded-md border p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Video inclusion criteria (applied before collection)
              </p>
              <CriteriaFilterBar
                entity="video"
                onChange={(group) => setVideoCriteria(group)}
                initialGroup={videoCriteria}
              />
            </section>
          ) : null}

          {collectComments !== false ? (
            <section className="space-y-2 rounded-md border p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Comment inclusion criteria (applied before collection)
              </p>
              <CriteriaFilterBar
                entity="comment"
                onChange={(group) => setCommentCriteria(group)}
                initialGroup={commentCriteria}
              />
            </section>
          ) : null}
          </>
        ) : null}
      </form>

      {running ? <JobProgressCard job={job} onCancel={cancelRun} cancelling={cancel.isPending} /> : null}

      {job?.status === "cancelled" ? (
        <Card className="flex items-start gap-3 border-muted p-4">
          <Ban className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
          <div className="text-sm">
            <p className="font-medium">Collection cancelled</p>
            <p className="text-muted-foreground">{job.message}</p>
          </div>
        </Card>
      ) : null}

      {submit.isError ? (
        <Card className="flex items-start gap-3 border-destructive/40 p-4">
          <CircleAlert className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden />
          <div className="text-sm">
            <p className="font-medium">Collection could not be submitted</p>
            <p className="text-muted-foreground">
              {(submit.error as Error).message}
            </p>
          </div>
        </Card>
      ) : null}

      {finished && result ? (
        <ResultSummary result={result} />
      ) : null}
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </Label>
      {children}
    </div>
  );
}

function JobProgressCard({
  job,
  onCancel,
  cancelling,
}: {
  job: { job_id: string; status: string; progress: { stage: string; discovered: number; succeeded: number; failed: number; message: string | null } } | undefined;
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
          <span className="font-mono text-xs text-muted-foreground">
            {job?.job_id}
          </span>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={onCancel}
          disabled={cancelling}
        >
          <Ban className="size-3.5" aria-hidden />
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

function ResultSummary({ result }: { result: CollectJobResult }) {
  const runsQuery = useRuns();
  const runNames = new Map(
    (runsQuery.data ?? [])
      .filter((run) => run.name)
      .map((run) => [run.run_id, run.name as string]),
  );
  if (result.target_count === 1) {
    const r = result.results[0];
    return (
      <Card className="space-y-3 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <RunStatusBadge status={r.status} />
            <span className="font-mono text-xs text-muted-foreground">
              {runNames.get(r.run_id) ?? r.run_id}
            </span>
          </div>
          <Button
            render={<Link href={`/runs/${r.run_id}`} />}
            nativeButton={false}
            variant="outline"
            size="sm"
          >
            View run details
          </Button>
        </div>
        <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <ResultStat label="Discovered" value={r.entities_discovered} />
          <ResultStat label="Created" value={r.entities_created} />
          <ResultStat label="Existing" value={r.entities_existing} />
          <ResultStat label="Failed" value={r.entities_failed} />
        </div>
        {r.comments_collected > 0 ? (
          <p className="text-xs text-muted-foreground">
            {formatNumber(r.comments_collected)} comment(s) collected.
          </p>
        ) : null}
        {r.errors.length > 0 ? (
          <div>
            <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Recorded errors
            </h4>
            <ErrorList errors={r.errors} />
          </div>
        ) : null}
      </Card>
    );
  }

  return (
    <Card className="space-y-3 p-4">
      <div className="flex items-center gap-2">
        <CheckCircle2 className="size-4 text-emerald-500" aria-hidden />
        <p className="text-sm font-medium">
          {formatNumber(result.target_count)} target(s) collected
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {result.results.map((r) => (
          <div key={r.run_id} className="space-y-2 rounded-md border p-3">
            <div className="flex items-center justify-between gap-2">
              <RunStatusBadge status={r.status} />
              <span className="font-mono text-xs text-muted-foreground">
                {runNames.get(r.run_id) ?? r.run_id}
              </span>
            </div>
            <p className="text-xs text-muted-foreground break-all">
              {r.target_url}
            </p>
            <p className="text-xs">
              {formatNumber(r.entities_discovered)} discovered ·{" "}
              {formatNumber(r.comments_collected)} comments
            </p>
          </div>
        ))}
      </div>
    </Card>
  );
}

function ResultStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border p-2">
      <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="text-lg font-semibold tabular-nums">{formatNumber(value)}</p>
    </div>
  );
}

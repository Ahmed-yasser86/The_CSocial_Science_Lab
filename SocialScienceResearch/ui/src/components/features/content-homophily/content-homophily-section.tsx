"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  Circle,
  Loader2,
  Play,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  CONTENT_HOMOPHILY_STAGES,
  STAGE_LABELS,
  listContentHomophily,
  startContentHomophily,
  useContentHomophily,
  type ContentHomophilyRecord,
  type ContentHomophilyResults,
} from "@/services/contentHomophily";

/**
 * CONTENT HOMOPHILY section (spec §22-§25).
 *
 * Opt-in + on-demand evidence layer usable from any supported network: the
 * researcher explicitly starts an analysis (which performs targeted
 * transcript collection for sampled videos only), watches the stage
 * checklist and embedding observability, then reads the CONTENT EVIDENCE
 * block. Nothing here ever runs automatically.
 */

function formatSigned(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return "—";
  const fixed = value.toFixed(digits);
  return value > 0 ? `+${fixed}` : fixed;
}

function StageChecklist({ record }: { record: ContentHomophilyRecord }) {
  const stages = record.progress.stages;
  return (
    <ol className="space-y-1" data-testid="chh-stage-checklist">
      {CONTENT_HOMOPHILY_STAGES.map((stage) => {
        const state = stages[stage] ?? "pending";
        return (
          <li key={stage} className="flex items-center gap-2 text-sm">
            {state === "done" ? (
              <CheckCircle2 className="size-4 text-emerald-500" aria-hidden />
            ) : state === "running" ? (
              <Loader2 className="size-4 animate-spin text-muted-foreground" aria-hidden />
            ) : state === "skipped" ? (
              <CircleAlert className="size-4 text-muted-foreground" aria-hidden />
            ) : (
              <Circle className="size-4 text-muted-foreground/40" aria-hidden />
            )}
            <span className={state === "pending" ? "text-muted-foreground" : ""}>
              {STAGE_LABELS[stage]}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function EmbeddingStats({ record }: { record: ContentHomophilyRecord }) {
  const p = record.progress;
  return (
    <div className="space-y-1 rounded-md border p-3 text-sm" data-testid="chh-embedding-stats">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Embedding Preparation
      </p>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3">
        <span>
          Videos:{" "}
          <span className="font-mono text-xs">
            {p.videos_processed ?? 0} / {p.videos_total ?? 0}
          </span>
        </span>
        <span>
          Reused / generated / failed:{" "}
          <span className="font-mono text-xs">
            {p.embeddings_reused ?? 0} / {p.embeddings_generated ?? 0} /{" "}
            {p.embedding_failures ?? 0}
          </span>
        </span>
        <span>
          Current:{" "}
          <span className="font-mono text-xs">{p.current_video ?? "—"}</span>
        </span>
        <span>
          Model: <span className="font-mono text-xs">{p.embedding_model ?? "—"}</span>
        </span>
        <span>
          Elapsed:{" "}
          <span className="font-mono text-xs">
            {p.elapsed_seconds != null ? `${p.elapsed_seconds}s` : "—"}
          </span>
        </span>
        <span>
          ETA:{" "}
          <span className="font-mono text-xs">
            {p.eta_seconds != null ? `${p.eta_seconds}s` : "—"}
          </span>
        </span>
      </div>
    </div>
  );
}

function ExecutionLog({ record }: { record: ContentHomophilyRecord }) {
  const [open, setOpen] = useState(false);
  const log = record.progress.log ?? [];
  if (log.length === 0) return null;
  return (
    <div data-testid="chh-execution-log">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? (
          <ChevronDown className="size-4" aria-hidden />
        ) : (
          <ChevronRight className="size-4" aria-hidden />
        )}
        Execution log ({log.length})
      </Button>
      {open ? (
        <ul className="max-h-64 space-y-0.5 overflow-y-auto rounded-md border p-2 font-mono text-[11px] text-muted-foreground">
          {log.map((entry, index) => (
            <li key={`${entry.ts}-${index}`}>
              [{entry.ts.slice(11, 19)}] {entry.message}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function ResultsBlock({ results }: { results: ContentHomophilyResults }) {
  const rows: [string, React.ReactNode][] = [
    [
      "Within-community similarity",
      <span key="w">{results.within_mean_similarity?.toFixed(3) ?? "—"}</span>,
    ],
    [
      "Between-community similarity",
      <span key="b">{results.between_mean_similarity?.toFixed(3) ?? "—"}</span>,
    ],
    [
      "Observed difference",
      <span key="d" className="font-semibold">
        {formatSigned(results.observed_difference, 3)}
      </span>,
    ],
    ["Null expectation", <span key="nm">{formatSigned(results.null_mean, 3)}</span>],
    ["Null SD", <span key="ns">{results.null_std?.toFixed(3) ?? "—"}</span>],
    ["Z-score", <span key="z">{formatSigned(results.z_score)}</span>],
    [
      "Permutation p-value",
      <span key="p">
        {results.permutation_p_value != null
          ? `< ${Math.max(results.permutation_p_value, 1e-3).toFixed(3)}`
          : "—"}
      </span>,
    ],
    [
      "Within pairs available / sampled",
      <span key="pw" className="font-mono text-xs">
        {results.pairs_available_within.toLocaleString()} /{" "}
        {results.pairs_sampled_within.toLocaleString()}
      </span>,
    ],
    [
      "Between pairs available / sampled",
      <span key="pb" className="font-mono text-xs">
        {results.pairs_available_between.toLocaleString()} /{" "}
        {results.pairs_sampled_between.toLocaleString()}
      </span>,
    ],
    [
      "Sampling fraction",
      <span key="sf">{(results.sampling_fraction * 100).toFixed(0)}%</span>,
    ],
    ["Pair cap", <span key="pc">{results.max_pair_cap.toLocaleString()}</span>],
    ["Permutations", <span key="np">{results.num_permutations}</span>],
    [
      "Transcript coverage",
      <span key="tc">
        {(results.transcript_coverage * 100).toFixed(0)}%
        {results.transcript_coverage < 1 ? " (partially unavailable)" : ""}
      </span>,
    ],
    [
      "Embedding model",
      <span key="em" className="font-mono text-xs">
        {results.embedding_model} ({results.embedding_model_version})
      </span>,
    ],
    ["Status", <span key="st">{results.status}</span>],
  ];
  return (
    <Card data-testid="chh-results">
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <Badge>CONTENT EVIDENCE</Badge>
          <Badge variant="outline">not an echo-chamber probability</Badge>
        </div>
        <CardDescription>
          Observed content structure only — no claims about user beliefs,
          causality, or polarization.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <dl className="divide-y rounded-md border">
          {rows.map(([label, node]) => (
            <div key={label} className="flex items-center justify-between gap-4 px-3 py-1.5">
              <dt className="text-sm text-muted-foreground">{label}</dt>
              <dd className="font-mono text-sm">{node}</dd>
            </div>
          ))}
        </dl>
        <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">
          {(results.disclaimers ?? []).map((d) => (
            <li key={d.slice(0, 32)}>{d}</li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

export function ContentHomophilySection() {
  const [runId, setRunId] = useState("");
  const [fraction, setFraction] = useState(0.1);
  const [numPermutations, setNumPermutations] = useState(1000);
  const [seed, setSeed] = useState("");
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  // Bumped on every explicit start so a re-run of the same analysis id gets a
  // fresh query (a terminal cached record must never mask the new run).
  const [runNonce, setRunNonce] = useState(0);

  const historyQuery = useQuery({
    queryKey: ["content-homophily", "list"],
    queryFn: () => listContentHomophily(),
  });
  const history = historyQuery.data?.items ?? [];

  // Auto-select the most recent analysis once so returning researchers see
  // their latest run instead of an empty state.
  const autoSelectedRef = useRef(false);
  useEffect(() => {
    if (autoSelectedRef.current || analysisId) return;
    const latest = history[0];
    if (latest && historyQuery.isSuccess) {
      setAnalysisId(latest.analysis_id);
      autoSelectedRef.current = true;
    }
  }, [history, historyQuery.isSuccess, analysisId]);

  const recordQuery = useContentHomophily(analysisId, runNonce);
  const record = recordQuery.data;

  const start = useMutation({
    mutationFn: () =>
      startContentHomophily({
        run_id: runId.trim() || undefined,
        sampling_fraction: fraction,
        num_permutations: numPermutations,
        random_seed: seed.trim() ? Number(seed) : undefined,
        tags: ["content_homophily"],
      }),
    onSuccess: (payload) => {
      setAnalysisId(payload.analysis_id);
      setRunNonce((n) => n + 1);
    },
  });

  const running = record?.status === "pending" || record?.status === "running";

  return (
    <div className="space-y-4" data-testid="content-homophily-section">
      <Card>
        <CardHeader>
          <CardTitle>Run a content homophily analysis</CardTitle>
          <CardDescription>
            Opt-in and on-demand: this collects transcripts ONLY for the
            sampled videos of the selected network scope, reuses the ingestion
            chunking/embedding pipeline, samples ≤10k pairs per operation with
            a seeded sampler, and runs a community-label permutation null.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-[1fr_auto_auto_auto_auto] md:items-end">
            <div className="space-y-1.5">
              <Label htmlFor="chh-run-id">Scope: Run ID (empty = whole network)</Label>
              <Input
                id="chh-run-id"
                placeholder="run_… (optional)"
                value={runId}
                onChange={(e) => setRunId(e.target.value)}
                disabled={running}
                data-testid="chh-run-id"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="chh-fraction">Sampling fraction</Label>
              <select
                id="chh-fraction"
                value={fraction}
                onChange={(e) => setFraction(Number(e.target.value))}
                disabled={running}
                className="h-9 rounded-md border bg-background px-2 text-sm"
                data-testid="chh-fraction"
              >
                <option value={0.05}>5%</option>
                <option value={0.1}>10%</option>
                <option value={0.2}>20%</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="chh-perms">Permutations</Label>
              <Input
                id="chh-perms"
                type="number"
                min={0}
                max={10000}
                value={numPermutations}
                onChange={(e) =>
                  setNumPermutations(
                    Math.max(0, Math.min(10000, Number(e.target.value) || 0)),
                  )
                }
                disabled={running}
                className="w-24"
                data-testid="chh-permutations"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="chh-seed">Seed</Label>
              <Input
                id="chh-seed"
                type="number"
                placeholder="42"
                value={seed}
                onChange={(e) => setSeed(e.target.value)}
                disabled={running}
                className="w-24"
                data-testid="chh-seed"
              />
            </div>
            <Button
              onClick={() => start.mutate()}
              disabled={running || start.isPending}
              data-testid="chh-start-button"
            >
              <Play className="size-4" aria-hidden />
              {start.isPending ? "Starting…" : "Run analysis"}
            </Button>
          </div>
          {start.isError ? (
            <p className="text-sm text-destructive">{String(start.error)}</p>
          ) : null}
        </CardContent>
      </Card>

      {!record ? (
        <Card
          className="p-8 text-center text-sm text-muted-foreground"
          data-testid="chh-empty"
        >
          No content homophily analysis yet. Configure the scope above and
          press “Run analysis” to opt in.
        </Card>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <Badge variant="secondary" data-testid="chh-status">
              {record.status.replace("_", " ")}
            </Badge>
            <span className="font-mono text-xs text-muted-foreground">
              {record.analysis_id}
            </span>
          </div>

          {record.error ? (
            <p className="text-sm text-destructive">{record.error}</p>
          ) : null}

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Analysis execution</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <StageChecklist record={record} />
                <EmbeddingStats record={record} />
                <ExecutionLog record={record} />
              </CardContent>
            </Card>

            {record.results ? (
              <ResultsBlock results={record.results} />
            ) : (
              <Card className="p-6 text-center text-sm text-muted-foreground">
                Results appear here when the statistical summary completes.
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import { Check, FileText, Loader2, Play, RotateCcw, Square, Terminal } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ReportViewer } from "./components/ReportViewer";
import { useAgentLogs, STAGE_LABELS, type StageStatus } from "./hooks/useAgentLogs";
import {
  runResearch,
  listRuns,
  getRun,
  cancelRun,
  type RunSession,
  type RunReportMeta,
} from "./lib/agentApi";

const STAGE_INFO: Record<string, { title: string; desc: string }> = {
  subject: {
    title: "Subject",
    desc: "Identity, profile and positioning of the subject.",
  },
  audience: {
    title: "Audience",
    desc: "Segments, narratives and vulnerabilities.",
  },
  ecosystem: {
    title: "Ecosystem",
    desc: "Actors, organizations and the information environment.",
  },
};
const STAGE_ORDER = ["subject", "audience", "ecosystem"];

function levelColor(level?: string): string {
  switch ((level || "").toUpperCase()) {
    case "ERROR":
      return "text-red-500";
    case "WARN":
      return "text-amber-500";
    case "SUCCESS":
      return "text-emerald-500";
    default:
      return "text-muted-foreground";
  }
}

function eventText(e: Record<string, any>): string {
  switch (e.type) {
    case "error":
      return e.message ?? "error";
    case "log":
      return e.message ?? "";
    case "stage_start":
      return `stage started: ${e.stage ?? ""}`;
    case "stage_done":
      return `stage completed: ${e.stage ?? ""}`;
    case "tool_call":
      return `tool call: ${e.tool ?? ""}`;
    case "tool_done":
      return `tool done: ${e.tool ?? ""}`;
    case "retriever":
      return `retriever ${e.action ?? ""} ${e.query ?? ""}`.trim();
    case "llm":
      return `llm ${e.action ?? ""} ${e.model ?? ""}`.trim();
    case "run_start":
      return "run started";
    case "done":
      return "run finished";
    case "connected":
      return "connected";
    default:
      return String(e.type ?? "");
  }
}

function eventLevel(e: Record<string, any>): string {
  if (e.type === "log") return (e.level ?? "INFO").toUpperCase();
  return e.type === "error" ? "ERROR" : "INFO";
}

function eventTag(e: Record<string, any>): string {
  if (e.type === "log") return (e.logger ?? "log").split(".").pop();
  return e.stage ?? e.tool ?? e.type ?? "log";
}

function StageStepper({
  stages,
  running,
}: {
  stages: { key: string; label: string; status: StageStatus }[];
  running: boolean;
}) {
  return (
    <ol className="relative space-y-1">
      {stages.map((s, i) => {
        const isLast = i === stages.length - 1;
        return (
          <li key={s.key} className="flex items-start gap-3">
            <div className="flex flex-col items-center">
              <span className="flex size-6 shrink-0 items-center justify-center rounded-full border border-border bg-background">
                {s.status === "done" ? (
                  <Check className="size-3.5 text-emerald-500" />
                ) : s.status === "active" ? (
                  <Loader2 className="size-3.5 animate-spin text-primary" />
                ) : s.status === "error" ? (
                  <span className="flex size-4 items-center justify-center rounded-full bg-destructive text-[10px] font-bold text-destructive-foreground">
                    !
                  </span>
                ) : (
                  <span className="size-2 rounded-full bg-muted-foreground/40" />
                )}
              </span>
              {!isLast ? (
                <span
                  className={
                    "my-0.5 w-px flex-1 " +
                    (s.status === "done" ? "bg-emerald-500/50" : "bg-border")
                  }
                />
              ) : null}
            </div>
            <div className="min-w-0 flex-1 pb-2">
              <div
                className={
                  "text-sm " +
                  (s.status === "pending"
                    ? "text-muted-foreground"
                    : "text-foreground") +
                  (s.status === "active" ? " font-medium" : "") +
                  (s.status === "error" ? " text-destructive" : "")
                }
              >
                {s.label}
              </div>
              <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
                {running && s.status === "active" ? "in progress" : s.status}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function ResearchConsole() {
  const { events, counts, currentStage, stages: pipelineStages, running, lastError, cancelled } = useAgentLogs();

  const [query, setQuery] = useState("");
  const [stages, setStages] = useState<string[]>([]);

  const [runs, setRuns] = useState<RunSession[]>([]);
  const [resumeRun, setResumeRun] = useState<string>("");

  const [busy, setBusy] = useState(false);
  const [runError, setRunError] = useState<string>("");

  const [activeRunId, setActiveRunId] = useState<string>("");
  const [activeReports, setActiveReports] = useState<RunReportMeta[]>([]);
  const [viewer, setViewer] = useState<{ runId: string; key: string; title: string } | null>(null);

  useEffect(() => {
    listRuns()
      .then(setRuns)
      .catch(() => setRuns([]));
  }, []);

  // When a run finishes (or is cancelled), refresh the reports panel + run list.
  const prevRunning = useRef(false);
  useEffect(() => {
    if (prevRunning.current && !running && activeRunId) {
      refreshRunReports(activeRunId);
      listRuns().then(setRuns).catch(() => setRuns([]));
    }
    prevRunning.current = running;
  }, [running, activeRunId]);

  function toggleStage(s: string) {
    setStages((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]));
    setResumeRun("");
  }

  function completeChain() {
    setStages([...STAGE_ORDER]);
    setResumeRun("");
  }

  async function refreshRunReports(runId: string) {
    try {
      const data = await getRun(runId);
      setActiveReports(data.reports);
    } catch {
      setActiveReports([]);
    }
  }

  async function openPast(runId: string) {
    setActiveRunId(runId);
    setRunError("");
    await refreshRunReports(runId);
  }

  async function runDirect() {
    if (busy) return;
    if (!query.trim() && !resumeRun) return;
    setBusy(true);
    setRunError("");
    try {
      const runStages = resumeRun ? undefined : stages.length ? stages : [...STAGE_ORDER];
      const res = await runResearch({
        user_query: query,
        stages: runStages,
        resume_run_id: resumeRun || undefined,
      });
      if (res.error) {
        setRunError(res.error);
      } else if (res.run_id) {
        setActiveRunId(res.run_id);
        setResumeRun("");
      }
    } finally {
      setBusy(false);
    }
  }

  async function stopRun() {
    if (!activeRunId) return;
    setBusy(true);
    try {
      const res = await cancelRun(activeRunId);
      if (res.error) setRunError(res.error);
    } finally {
      setBusy(false);
    }
  }

  const runningStages = resumeRun ? null : stages.length ? stages : [...STAGE_ORDER];

  return (
    <div className="flex h-[calc(100dvh-3.5rem)] min-h-0 flex-col">
      {/* Top bar */}
      <header className="flex items-center justify-between gap-4 border-b border-border px-5 py-3">
        <div className="flex items-center gap-2">
          <span className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground text-[11px] font-semibold">
            AI
          </span>
          <div>
            <h1 className="text-sm font-semibold leading-tight">Research Agent Console</h1>
            <p className="text-[11px] text-muted-foreground">
              Graph-RAG intelligence pipeline · subject / audience / ecosystem
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {running || busy ? (
            <Badge variant="secondary" className="gap-1">
              <Loader2 className="size-3 animate-spin" /> Running
            </Badge>
          ) : (
            <Badge variant="outline" className="gap-1">
              <span className="size-1.5 rounded-full bg-emerald-500" /> Idle
            </Badge>
          )}
          {currentStage ? (
            <Badge variant="secondary" className="capitalize">
              {STAGE_LABELS[currentStage] ?? currentStage}
            </Badge>
          ) : null}
        </div>
      </header>

      {/* Body */}
      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[360px_minmax(0,1fr)]">
        {/* Configuration column */}
        <div className="flex min-h-0 flex-col gap-4 overflow-y-auto border-border p-5 lg:border-r">
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground" htmlFor="subject">
              Subject to research
            </label>
            <Textarea
              id="subject"
              placeholder="A public figure, organization or topic…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="min-h-20 text-sm"
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">Stages</span>
              <button
                type="button"
                onClick={completeChain}
                className="text-[11px] text-primary hover:underline"
              >
                Select all
              </button>
            </div>
            <div className="grid grid-cols-1 gap-2">
              {STAGE_ORDER.map((s) => {
                const on = stages.includes(s);
                return (
                  <button
                    key={s}
                    type="button"
                    onClick={() => toggleStage(s)}
                    className={
                      "flex items-start gap-3 rounded-lg border p-3 text-left transition-colors " +
                      (on
                        ? "border-primary bg-primary/5"
                        : "border-border hover:border-foreground/30 hover:bg-muted/40")
                    }
                  >
                    <span
                      className={
                        "mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full border " +
                        (on ? "border-primary bg-primary text-primary-foreground" : "border-muted-foreground/40")
                      }
                    >
                      {on ? <Check className="size-3" /> : null}
                    </span>
                    <span className="min-w-0">
                      <span className="block text-sm font-medium capitalize">{s}</span>
                      <span className="block text-[11px] text-muted-foreground">
                        {STAGE_INFO[s].desc}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {running && activeRunId ? (
            <Button onClick={stopRun} disabled={busy} variant="destructive" className="w-full">
              <Square className="size-4" /> Stop run
            </Button>
          ) : (
            <Button onClick={runDirect} disabled={busy || (!query.trim() && !resumeRun)} className="w-full">
              {busy ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
              {resumeRun ? "Resume run" : "Run pipeline"}
            </Button>
          )}

          {runError ? (
            <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-[11px] text-destructive">
              {runError}
            </div>
          ) : null}

          {cancelled ? (
            <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-[11px] text-amber-600">
              Run stopped. Partial results (if any) are kept in the active run.
            </div>
          ) : null}

          <Separator />

          <div className="space-y-2">
            <span className="text-xs font-medium text-muted-foreground">Resume a past run</span>
            <select
              className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
              value={resumeRun}
              onChange={(e) => {
                const v = e.target.value;
                setResumeRun(v);
                if (v) openPast(v);
              }}
            >
              <option value="">Select a previous run…</option>
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.subject || r.id} — {(r.completed_reports ?? []).join(", ") || "none"}
                </option>
              ))}
            </select>
            <p className="text-[11px] text-muted-foreground">
              Pick an incomplete run, then press “Resume run” to generate the remaining stages.
            </p>
          </div>

          {activeRunId ? (
            <div className="rounded-lg border border-border bg-muted/30 p-3 text-[11px]">
              <span className="text-muted-foreground">Active run:</span>{" "}
              <span className="font-mono">{activeRunId}</span>
            </div>
          ) : null}
        </div>

        {/* Results column */}
        <div className="flex min-h-0 flex-col">
          <Tabs defaultValue="reports" className="flex min-h-0 flex-1 flex-col">
            <div className="flex items-center justify-between border-b border-border px-4 py-2">
              <TabsList variant="line">
                <TabsTrigger value="reports" className="gap-1.5">
                  <FileText className="size-4" /> Reports
                </TabsTrigger>
                <TabsTrigger value="activity" className="gap-1.5">
                  <Terminal className="size-4" /> Activity
                  {events.length > 0 ? <Badge variant="secondary" className="ml-1">{events.length}</Badge> : null}
                </TabsTrigger>
              </TabsList>
              <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                <RotateCcw className="size-3.5" /> {counts.tokens} tokens
              </div>
            </div>

            <TabsContent value="reports" className="min-h-0 flex-1 overflow-y-auto p-4">
              {activeReports.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-muted-foreground">
                  <FileText className="size-8 opacity-40" />
                  <p className="text-sm">No reports for this run yet.</p>
                  <p className="text-[11px]">
                    Configure a subject and stages on the left, then run the pipeline.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {activeReports.map((r) => (
                    <Card key={r.report_type} className="overflow-hidden">
                      <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0 pb-2">
                        <CardTitle className="text-sm capitalize">{r.report_type}</CardTitle>
                        <Badge variant={r.completed ? "secondary" : "outline"}>
                          {r.completed ? "ready" : "pending"}
                        </Badge>
                      </CardHeader>
                      <CardContent className="space-y-2">
                        <p className="line-clamp-2 text-[11px] text-muted-foreground">
                          {r.summary || "No summary."}
                        </p>
                        <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                          <span>{r.sources?.length ?? 0} sources</span>
                          <Button size="sm" variant="ghost" onClick={() => setViewer({ runId: activeRunId, key: r.report_type, title: r.report_type })}>
                            Open
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent value="activity" className="min-h-0 flex-1 overflow-y-auto p-4">
              <div className="space-y-4">
                {/* Primary view: pipeline stage stepper (observability) */}
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0 pb-2">
                    <CardTitle className="text-sm">Pipeline progress</CardTitle>
                    <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                      <RotateCcw className="size-3.5" /> {counts.tokens} tokens
                      {counts.error > 0 ? (
                        <Badge variant="destructive" className="ml-1">{counts.error} error{counts.error > 1 ? "s" : ""}</Badge>
                      ) : null}
                    </div>
                  </CardHeader>
                  <CardContent>
                    {events.length === 0 ? (
                      <p className="text-[12px] text-muted-foreground">
                        No activity yet. Configure a subject and run the pipeline to see live progress.
                      </p>
                    ) : (
                      <StageStepper stages={pipelineStages} running={running || busy} />
                    )}
                  </CardContent>
                </Card>

                {/* Never hide failures: surface the latest error prominently. */}
                {lastError ? (
                  <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-[11px] text-destructive">
                    <span className="font-semibold">Run failed:</span> {lastError}
                  </div>
                ) : null}

                {/* Details: full execution log (progressive disclosure) */}
                <Card className="overflow-hidden">
                  <CardHeader className="pb-2">
                   <CardTitle className="text-[11px] font-medium text-muted-foreground">
                       Backend console {events.length > 0 ? `(${events.length})` : ""}
                     </CardTitle>
                  </CardHeader>
                  <CardContent className="max-h-72 overflow-y-auto p-3 font-mono text-[12px] leading-relaxed">
                    {events.length === 0 ? (
                      <p className="text-muted-foreground">Waiting for activity…</p>
                    ) : (
                      events.map((e, i) => {
                        const ev = e as Record<string, any>;
                        return (
                           <div key={i} className="border-b border-border/50 py-1">
                             <span className="text-muted-foreground/70">
                               {ev.ts ? String(ev.ts).slice(11, 19) : ""}
                             </span>{" "}
                             <span className={levelColor(eventLevel(ev))}>
                               [{String(eventTag(ev)).toUpperCase()}]
                             </span>{" "}
                             <span className={ev.type === "log" ? levelColor(eventLevel(ev)) : "text-foreground/90"}>{eventText(ev)}</span>
                           </div>
                        );
                      })
                    )}
                  </CardContent>
                </Card>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>

      {viewer ? (
        <ReportViewer runId={viewer.runId} reportKey={viewer.key} title={viewer.title} onClose={() => setViewer(null)} />
      ) : null}
    </div>
  );
}

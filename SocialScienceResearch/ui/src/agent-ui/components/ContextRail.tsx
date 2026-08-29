"use client";

import { useEffect, useState } from "react";
import { useCoAgent } from "@copilotkit/react-core";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { IntelligenceGraphView } from "./IntelligenceGraphView";
import { ReportCard } from "./ReportCard";
import { SourcesList } from "./SourcesList";
import { CostBadge } from "./CostBadge";
import { ReportViewer } from "./ReportViewer";
import {
  runResearch,
  listRuns,
  getRun,
  type RunSession,
  type RunReportMeta,
} from "../lib/agentApi";
import type { LogEvent, LogCounts, ReportVal, ResearchAgentState } from "../lib/logSchema";

const STAGES = ["subject", "audience", "ecosystem"] as const;
const ALL_STAGES = [...STAGES];

export function ContextRail({
  events,
  counts,
  currentStage,
  onShowLogs,
}: {
  events: LogEvent[];
  counts: LogCounts;
  currentStage?: string;
  onShowLogs: () => void;
}) {
  const { state } = useCoAgent<ResearchAgentState>({
    name: "research_agent",
    initialState: {
      user_initial_query: "",
      input_paths: {
        subject_profile_path: "",
        briefing_1_path: "",
        briefing_2_path: "",
      },
      report_plan: null,
    } as ResearchAgentState,
  });

  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [stages, setStages] = useState<string[]>([]);

  const [runs, setRuns] = useState<RunSession[]>([]);
  const [resumeRun, setResumeRun] = useState<string>("");

  const [activeRunId, setActiveRunId] = useState<string>("");
  const [activeReports, setActiveReports] = useState<RunReportMeta[]>([]);
  const [runError, setRunError] = useState<string>("");

  const [viewer, setViewer] = useState<{ runId: string; key: string; title: string } | null>(null);

  const reports = (state?.reports ?? {}) as Record<string, ReportVal>;

  useEffect(() => {
    listRuns()
      .then(setRuns)
      .catch(() => setRuns([]));
  }, []);

  function toggleStage(s: string) {
    setStages((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]));
  }

  function completeChain() {
    setStages([...ALL_STAGES]);
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

  async function runDirect() {
    if (!query.trim() && !resumeRun) return;
    setBusy(true);
    setRunError("");
    onShowLogs();
    try {
      const runStages = resumeRun ? undefined : stages.length ? stages : ALL_STAGES;
      const res = await runResearch({
        user_query: query,
        stages: runStages,
        resume_run_id: resumeRun || undefined,
      });
      if (res.error) {
        setRunError(res.error);
      } else if (res.run_id) {
        setActiveRunId(res.run_id);
        await refreshRunReports(res.run_id);
        loadRuns();
      }
    } finally {
      setBusy(false);
    }
  }

  async function loadRuns() {
    try {
      setRuns(await listRuns());
    } catch {
      /* ignore */
    }
  }

  async function openPast(runId: string) {
    setActiveRunId(runId);
    setRunError("");
    await refreshRunReports(runId);
  }

  return (
    <aside className="flex min-h-0 w-full flex-col gap-3 overflow-y-auto border-l border-border p-3 lg:w-[28rem]">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Pipeline</CardTitle>
        </CardHeader>
        <CardContent>
          <IntelligenceGraphView activeStage={currentStage} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Stage</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="grid grid-cols-2 gap-2">
            {STAGES.map((s) => {
              const on = stages.includes(s);
              return (
                <Button
                  key={s}
                  size="sm"
                  variant={on ? "default" : "outline"}
                  onClick={() => toggleStage(s)}
                  className="capitalize whitespace-nowrap"
                >
                  {s}
                </Button>
              );
            })}
            <Button
              size="sm"
              variant="secondary"
              onClick={completeChain}
              className="col-span-2 whitespace-nowrap"
            >
              Complete chain
            </Button>
          </div>
          <p className="text-[11px] text-muted-foreground">
            Pick a stage to run on its own, or “Complete chain” to run the full
            subject → audience → ecosystem pipeline.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Run research</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <Textarea
            placeholder="Subject to research (e.g. a public figure or organization)…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="min-h-16 text-sm"
          />
          <div className="flex gap-2">
            <Button size="sm" onClick={runDirect} disabled={busy || (!query.trim() && !resumeRun)}>
              {busy ? "Running…" : "Run"}
            </Button>
            <Button size="sm" variant="outline" onClick={onShowLogs}>
              Logs
            </Button>
          </div>
          {runError ? <p className="text-[11px] text-destructive">{runError}</p> : null}
          {activeRunId ? (
            <p className="text-[11px] text-muted-foreground">Last run: {activeRunId}</p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Resume / past runs</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <select
            className="w-full rounded-md border border-border bg-background px-2 py-1 text-xs"
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
            Resume an incomplete run: select it, then press “Run” to generate the
            remaining reports.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0 pb-2">
          <CardTitle className="text-sm">Cost</CardTitle>
          <CostBadge tokens={counts.tokens} />
        </CardHeader>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Retrieval</CardTitle>
        </CardHeader>
        <CardContent>
          <SourcesList events={events} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Reports</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {activeReports.length > 0 ? (
            <div className="space-y-2">
              {activeReports.map((r) => (
                <div
                  key={r.report_type}
                  className="flex items-center justify-between rounded-md border border-border px-2 py-1"
                >
                  <span className="text-xs capitalize">{r.report_type}</span>
                  <Button size="sm" variant="ghost" onClick={() => setViewer({ runId: activeRunId, key: r.report_type, title: r.report_type })}>
                    Open
                  </Button>
                </div>
              ))}
            </div>
          ) : Object.keys(reports).length === 0 ? (
            <p className="text-xs text-muted-foreground">No reports yet.</p>
          ) : (
            Object.entries(reports).map(([k, v]) => <ReportCard key={k} kind={k} report={v} />)
          )}
        </CardContent>
      </Card>

      {viewer ? (
        <ReportViewer
          runId={viewer.runId}
          reportKey={viewer.key}
          title={viewer.title}
          onClose={() => setViewer(null)}
        />
      ) : null}
    </aside>
  );
}

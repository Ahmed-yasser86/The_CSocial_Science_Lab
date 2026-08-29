export interface RunResearchInput {
  user_query?: string;
  subject_profile_path?: string;
  briefing_1_path?: string;
  briefing_2_path?: string;
  stages?: string[];
  resume_run_id?: string;
}

export interface RunResearchResult {
  ok: boolean;
  run_id?: string;
  report_plan?: string[];
  summary?: unknown;
  error?: string;
}

export async function runResearch(input: RunResearchInput): Promise<RunResearchResult> {
  // Hit the backend directly (NEXT_PUBLIC_AGENT_BACKEND_URL) to avoid the
  // Next.js proxy, which buffers POST bodies / SSE and causes hangs + 500s.
  const base = process.env.NEXT_PUBLIC_AGENT_BACKEND_URL ?? "";
  try {
    const res = await fetch(`${base}/api/agent/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    const text = await res.text();
    let data: RunResearchResult | null = null;
    try {
      data = text ? (JSON.parse(text) as RunResearchResult) : null;
    } catch {
      // Backend returned non-JSON (e.g. Starlette's plain-text 500). Surface it
      // as a readable error rather than throwing an unhandled parse failure.
      data = null;
    }
    if (!res.ok || !data || data.ok === false) {
      return {
        ok: false,
        error:
          data && data.error
            ? String(data.error)
            : `Run failed (HTTP ${res.status}): ${text.slice(0, 300)}`,
      };
    }
    return data;
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) };
  }
}

export interface RunSession {
  id: string;
  subject: string;
  status: string;
  report_plan: string[];
  completed_reports: string[];
  run_folder: string;
  created_at: string;
}

export async function listRuns(): Promise<RunSession[]> {
  const base = process.env.NEXT_PUBLIC_AGENT_BACKEND_URL ?? "";
  const res = await fetch(`${base}/api/agent/runs`);
  const data = await res.json();
  return data.runs ?? [];
}

export interface RunReportMeta {
  report_type: string;
  path?: string;
  summary: string;
  sources: { url: string; title: string; note: string }[];
  completed: number;
}

export async function getRun(runId: string): Promise<{ session: RunSession; reports: RunReportMeta[] }> {
  const base = process.env.NEXT_PUBLIC_AGENT_BACKEND_URL ?? "";
  const res = await fetch(`${base}/api/agent/runs/${runId}`);
  if (!res.ok) throw new Error("run not found");
  return res.json();
}

export interface RunReportContent {
  report_type: string;
  path?: string;
  content: string;
  summary: string;
  sources: { url: string; title: string; note: string }[];
}

export async function getRunReport(runId: string, reportKey: string): Promise<RunReportContent> {
  const base = process.env.NEXT_PUBLIC_AGENT_BACKEND_URL ?? "";
  const res = await fetch(`${base}/api/agent/runs/${runId}/reports/${reportKey}`);
  if (!res.ok) throw new Error("report not found");
  return res.json();
}

export async function cancelRun(runId: string): Promise<{ ok: boolean; cancelled?: boolean; error?: string }> {
  const base = process.env.NEXT_PUBLIC_AGENT_BACKEND_URL ?? "";
  try {
    const res = await fetch(`${base}/api/agent/run/${encodeURIComponent(runId)}/cancel`, {
      method: "POST",
    });
    const data = await res.json();
    if (!res.ok || !data || data.ok === false) {
      return { ok: false, error: data?.error ? String(data.error) : `Cancel failed (HTTP ${res.status})` };
    }
    return { ok: true, cancelled: true };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) };
  }
}

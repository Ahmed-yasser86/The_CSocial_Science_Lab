"use client";

import { useEffect, useState } from "react";
import { getRunReport, type RunReportContent } from "../lib/agentApi";

export function ReportViewer({
  runId,
  reportKey,
  title,
  onClose,
}: {
  runId: string;
  reportKey: string;
  title: string;
  onClose: () => void;
}) {
  const [report, setReport] = useState<RunReportContent | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setReport(null);
    setError(null);
    getRunReport(runId, reportKey)
      .then((r) => {
        if (!cancelled) setReport(r);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e?.message ?? e));
      });
    return () => {
      cancelled = true;
    };
  }, [runId, reportKey]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="flex max-h-[85vh] w-full max-w-3xl flex-col rounded-lg border border-border bg-background shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-2">
          <h2 className="text-sm font-semibold capitalize">{title} report</h2>
          <button
            className="rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-muted"
            onClick={onClose}
          >
            Close
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-auto p-4">
          {error ? (
            <p className="text-sm text-destructive">{error}</p>
          ) : !report ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : (
            <pre className="whitespace-pre-wrap break-words font-mono text-[12px] leading-relaxed">
              {report.content || "(empty report)"}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}

"use client";

import Link from "next/link";
import { useRuns } from "@/services/queries";
import { RunStatusBadge } from "@/components/features/run-status-badge";
import { LoadingState } from "@/components/features/state";
import { Card } from "@/components/ui/card";
import { formatDateTime } from "@/lib/format";

/**
 * Workspace-scoped recent-runs list. Runs live inside the ACTIVE workspace
 * (its own database), so this panel always reflects the entered workspace —
 * never a global feed.
 */
export function RecentRunsPanel({ limit = 5 }: { limit?: number }) {
  const runsQuery = useRuns();
  const recent = runsQuery.data?.slice(-limit).reverse() ?? [];

  if (runsQuery.isLoading) {
    return <LoadingState label="Loading runs…" />;
  }

  if (recent.length === 0) {
    return (
      <Card
        className="p-4 text-sm text-muted-foreground"
        data-testid="runs-empty-state"
      >
        No runs yet in this workspace. Every collection is recorded here with
        its status, targets, and errors.
      </Card>
    );
  }

  return (
    <ul className="space-y-2">
      {recent.map((run) => (
        <li key={run.run_id}>
          <Link
            href={`/runs/${run.run_id}`}
            className="block rounded-md border p-3 transition-colors hover:bg-muted"
          >
            <div className="flex items-center justify-between gap-2">
              <code className="text-xs">{run.name ?? run.run_id}</code>
              <RunStatusBadge status={run.status} />
            </div>
            <p className="mt-1 truncate text-xs text-muted-foreground">
              {run.target_url}
            </p>
            <p className="text-[10px] text-muted-foreground">
              {formatDateTime(run.started_at)}
            </p>
          </Link>
        </li>
      ))}
    </ul>
  );
}

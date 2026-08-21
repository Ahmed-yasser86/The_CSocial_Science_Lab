"use client";

import Link from "next/link";
import { useRuns } from "@/services/queries";
import { CollectTargetForm } from "@/components/features/collect-target-form";
import { RunStatusBadge } from "@/components/features/run-status-badge";
import { LoadingState } from "@/components/features/state";
import { Card } from "@/components/ui/card";
import { formatDateTime } from "@/lib/format";

export function ResearchDesk() {
  const runsQuery = useRuns();
  const recent = runsQuery.data?.slice(-5).reverse() ?? [];

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
      <div className="space-y-6">
        <section>
          <h2 className="mb-3 text-sm font-medium">Collect data</h2>
          <CollectTargetForm />
        </section>
      </div>

      <aside className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium">Recent runs</h2>
          <Link
            href="/runs"
            className="text-xs text-muted-foreground underline-offset-2 hover:underline"
          >
            View all
          </Link>
        </div>
        {runsQuery.isLoading ? (
          <LoadingState label="Loading runs…" />
        ) : recent.length === 0 ? (
          <Card className="p-4 text-sm text-muted-foreground">
            No runs yet. Every collection is recorded here with its status,
            targets, and errors.
          </Card>
        ) : (
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
        )}
      </aside>
    </div>
  );
}

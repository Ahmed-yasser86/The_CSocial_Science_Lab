import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { RunDetail } from "@/components/features/run-detail";
import { serverJson } from "@/services/server-data";

export default async function RunPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = await params;
  const run = await serverJson<{ name: string | null }>(`/runs/${runId}`);
  const name = run?.name ?? runId;
  return (
    <div className="space-y-4">
      <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-xs text-muted-foreground">
        <Link href="/runs" className="underline-offset-2 hover:underline">
          Runs
        </Link>
        <ChevronRight className="size-3" aria-hidden />
        <span className="truncate">{name}</span>
      </nav>
      <RunDetail runId={runId} />
    </div>
  );
}

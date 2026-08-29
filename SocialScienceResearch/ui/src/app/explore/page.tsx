import type { Metadata } from "next";
import { Compass } from "@/components/ui/icon";
import { RecordExplorer } from "@/components/features/explorer/record-explorer";

export const metadata: Metadata = {
  title: "Explorer",
};

export default async function ExplorePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const entity =
    typeof params.entity === "string" ? params.entity : undefined;
  const q = typeof params.q === "string" ? params.q : undefined;
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <Compass className="size-5 text-muted-foreground" aria-hidden />
          Record explorer
        </h1>
        <p className="text-sm text-muted-foreground">
          Browse the latest observed rows for any entity, filter with the same
          operators as the research-query evaluator, and inspect the raw payload
          and collection provenance of each record. Data is observed, never
          estimated.
        </p>
      </header>
      <RecordExplorer initialEntity={entity} initialQuery={q} />
    </div>
  );
}


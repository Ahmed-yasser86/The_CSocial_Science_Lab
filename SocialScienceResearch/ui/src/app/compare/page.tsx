import type { Metadata } from "next";
import { Scale } from "@/components/ui/icon";
import { ComparisonWorkspace } from "@/components/features/comparison/comparison-workspace";

export const metadata: Metadata = {
  title: "Compare",
};

export default function ComparePage() {
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <Scale className="size-5 text-muted-foreground" aria-hidden />
          Comparison workspace
        </h1>
        <p className="text-sm text-muted-foreground">
          Compare videos, channels, upload-date periods, cohorts and collection
          runs with an explicit normalization. Statistics are computed over the
          compared set only; outliers are flagged, never dropped.
        </p>
      </header>
      <ComparisonWorkspace />
    </div>
  );
}


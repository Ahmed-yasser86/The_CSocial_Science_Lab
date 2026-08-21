import type { Metadata } from "next";
import { Share2 } from "lucide-react";
import { NetworkSummaryView } from "@/components/features/network-summary-view";

export const metadata: Metadata = {
  title: "Network",
};

export default function NetworkPage() {
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <Share2 className="size-5 text-muted-foreground" aria-hidden />
          Recommendation network
        </h1>
        <p className="text-sm text-muted-foreground">
          Aggregate analysis of observed recommendation relationships. The graph
          is rebuilt on demand from persisted edges and can be sliced by a single
          collection run for temporal analysis.
        </p>
      </header>
      <NetworkSummaryView />
    </div>
  );
}

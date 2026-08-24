import type { Metadata } from "next";
import { ResearchDesk } from "@/components/features/research-desk";

export const metadata: Metadata = {
  title: "Collect",
};

export default function CollectPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold tracking-tight">Collection</h1>
        <p className="text-sm text-muted-foreground">
          Trigger a channel, video, or recommendation-observation run. Collection
          calls the acquisition library over the network and can take minutes for
          large channels. Every run is recorded in the provenance ledger, even if
          it fails partway through.
        </p>
      </header>
      <ResearchDesk />
      <p className="text-xs text-muted-foreground">
        Recommendation runs observe each video’s “Up Next” rail through a
        layered provider strategy (library fields, the INNERTUBE /next endpoint,
        and raw watch-page dumps) and rank every edge by its position in the
        feed. If every provider returns nothing, the run records an explicit
        unsupported error instead of fabricating edges.
      </p>
    </div>
  );
}

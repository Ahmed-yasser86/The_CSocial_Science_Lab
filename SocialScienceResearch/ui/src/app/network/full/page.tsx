import type { Metadata } from "next";
import { GitFork } from "@/components/ui/icon";
import { FullNetworkView } from "@/components/features/network-full/full-network-view";

export const metadata: Metadata = {
  title: "Full Network",
};

export default function NetworkFullPage() {
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <GitFork className="size-5 text-muted-foreground" aria-hidden />
          Full network analytics
        </h1>
        <p className="text-sm text-muted-foreground">
          Density, reciprocity, degree percentiles, clustering, components,
          communities and HITS ranks for the whole observed recommendation
          network — plus per-run temporal slices, edge listings and
          GraphML / edgelist / GEXF exports.
        </p>
      </header>
      <FullNetworkView />
    </div>
  );
}


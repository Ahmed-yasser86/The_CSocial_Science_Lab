import type { Metadata } from "next";
import { FolderOpen } from "lucide-react";
import { DatasetLibrary } from "@/components/features/datasets/dataset-library";

export const metadata: Metadata = {
  title: "Datasets",
};

export default function DatasetsPage() {
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <FolderOpen className="size-5 text-muted-foreground" aria-hidden />
          Datasets
        </h1>
        <p className="text-sm text-muted-foreground">
          Materialized, immutable row sets built from the corpus. Inspect
          per-dataset quality, browse member rows, and export as CSV or JSON.
        </p>
      </header>
      <DatasetLibrary />
    </div>
  );
}

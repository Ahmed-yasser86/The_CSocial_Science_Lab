"use client";

import { useState } from "react";
import { Plus, Loader2, Library, GitCompareArrows } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyState, ErrorState, LoadingState } from "@/components/features/state";
import { SampleCard } from "@/components/features/samples/sample-card";
import { SampleOverlap, SampleCompareResultView } from "@/components/features/samples/sample-overlap";
import { SampleBuilder } from "@/components/features/samples/sample-builder";
import { useSampleList, useDeleteSample, useCompareSamples } from "@/services/samples";
import { useToast } from "@/components/ui/toast";

export function SampleLibrary() {
  const { toast } = useToast();
  const [tab, setTab] = useState<"library" | "compare">("library");
  const [builderOpen, setBuilderOpen] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [compareResult, setCompareResult] = useState<unknown>(null);

  const list = useSampleList();
  const samples = list.data?.pages.flatMap((page) => page.items) ?? [];

  const del = useDeleteSample();
  const compare = useCompareSamples();

  function toggleSelect(sampleId: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(sampleId)) next.delete(sampleId);
      else next.add(sampleId);
      return next;
    });
  }

  function runCompare() {
    const ids = [...selected];
    if (ids.length < 2) {
      toast({
        variant: "destructive",
        title: "Select at least two samples",
        description: "Pairwise overlap needs two or more samples.",
      });
      return;
    }
    compare.mutate(ids, {
      onSuccess: (result) => {
        setCompareResult(result);
        setTab("compare");
      },
      onError: (error) => {
        toast({
          variant: "destructive",
          title: "Comparison failed",
          description: error instanceof Error ? error.message : "Unknown error",
        });
      },
    });
  }

  function handleDelete(sampleId: string) {
    del.mutate(sampleId, {
      onSuccess: () => {
        toast({
          title: "Sample deleted",
          description: sampleId,
        });
      },
      onError: (error) => {
        toast({
          variant: "destructive",
          title: "Could not delete sample",
          description: error instanceof Error ? error.message : "Unknown error",
        });
      },
    });
  }

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex-shrink-0 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Tabs value={tab} onValueChange={(value) => setTab(value as "library" | "compare")}>
              <TabsList>
                <TabsTrigger value="library">
                  <Library className="size-4" aria-hidden />
                  Library
                </TabsTrigger>
                <TabsTrigger value="compare">
                  <GitCompareArrows className="size-4" aria-hidden />
                  Compare
                </TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
          <Button type="button" variant="outline" size="sm" onClick={() => setBuilderOpen(true)}>
            <Plus className="size-4" aria-hidden />
            New sample
          </Button>
        </div>
        <p className="text-sm text-muted-foreground">
          {tab === "library"
            ? "Immutable, auditable samples drawn from your corpus — each records its criteria and exact membership."
            : "Compute pairwise overlap, union and Jaccard similarity between saved samples."}
        </p>
      </div>

      {tab === "library" ? (
        <div className="flex flex-col gap-4">
          {list.isLoading ? (
            <LoadingState label="Loading samples…" />
          ) : list.isError ? (
            <ErrorState
              message={
                list.error instanceof Error
                  ? list.error.message
                  : "Failed to load samples"
              }
              retry={() => list.refetch()}
            />
          ) : samples.length === 0 ? (
            <EmptyState
              title="No samples yet"
              description="Preserve a population definition and its exact membership as an immutable, reproducible sample."
              action={
                <Button type="button" variant="outline" size="sm" onClick={() => setBuilderOpen(true)}>
                  <Plus className="size-4" aria-hidden />
                  Create your first sample
                </Button>
              }
            />
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
              {samples.map((sample) => (
                <SampleCard key={sample.sample_id} sample={sample} onDelete={handleDelete} />
              ))}
            </div>
          )}

          {list.hasNextPage ? (
            <div className="flex justify-center">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => void list.fetchNextPage()}
                disabled={list.isFetchingNextPage}
              >
                {list.isFetchingNextPage ? (
                  <>
                    <Loader2 className="size-3.5 animate-spin" aria-hidden />
                    Loading…
                  </>
                ) : (
                  "Load more samples"
                )}
              </Button>
            </div>
          ) : null}
        </div>
      ) : (
        <div className="space-y-4">
          <SampleOverlap
            samples={samples}
            selected={selected}
            onSelect={toggleSelect}
          />
          <div className="flex items-center gap-3">
            <Button type="button" variant="outline" size="sm" onClick={runCompare}>
              <GitCompareArrows className="size-3.5" aria-hidden />
              Compare selected
            </Button>
            {selected.size > 0 ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setSelected(new Set())}
              >
                Clear selection
              </Button>
            ) : null}
            {compareResult ? (
              <Button type="button" variant="outline" size="sm" onClick={runCompare}>
                Re-run
              </Button>
            ) : null}
          </div>
          {compare.isPending ? (
            <LoadingState label="Comparing samples…" />
          ) : compareResult ? (
            <SampleCompareResultView result={compareResult as Parameters<typeof SampleCompareResultView>[0]["result"]} />
          ) : (
            <EmptyState
              title="No comparison yet"
              description="Select samples above and press Compare selected."
            />
          )}
        </div>
      )}

      <SampleBuilder open={builderOpen} onOpenChange={setBuilderOpen} />
    </div>
  );
}

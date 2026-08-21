"use client";

import { useState } from "react";
import { Plus, Download, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState, ErrorState, LoadingState } from "@/components/features/state";
import { DatasetBuilder } from "@/components/features/datasets/dataset-builder";
import { QualityPanel } from "@/components/features/datasets/quality-panel";
import {
  listDatasets,
  getDatasetMembers,
  getDatasetExportUrl,
  deleteDataset,
} from "@/services/datasets";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useToast } from "@/components/ui/toast";
import { formatDateTime } from "@/lib/format";
import type { Dataset, Paginated } from "@/lib/dataset-types";

export function DatasetLibrary() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [builderOpen, setBuilderOpen] = useState(false);
  const [selected, setSelected] = useState<Dataset | null>(null);
  const [selectedTab, setSelectedTab] = useState<"quality" | "members">("quality");

  const query = useQuery({
    queryKey: ["datasets", "library"],
    queryFn: () => listDatasets(),
  });

  const del = useMutation({
    mutationFn: (datasetId: string) => deleteDataset(datasetId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["datasets"] });
      toast({ title: "Dataset deleted" });
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Could not delete dataset",
        description: error instanceof Error ? error.message : "Unknown error",
      });
    },
  });

  const datasets = query.data?.items ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {query.isLoading
            ? "Loading…"
            : query.data?.total !== null && query.data?.total !== undefined
              ? `${query.data.total.toLocaleString()} datasets`
              : `${datasets.length} datasets`}
        </p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setBuilderOpen(true)}
        >
          <Plus className="size-4" aria-hidden />
          New dataset
        </Button>
      </div>

      {query.isLoading ? (
        <LoadingState label="Loading datasets…" />
      ) : query.isError ? (
        <ErrorState
          message={
            query.error instanceof Error
              ? query.error.message
              : "Failed to load datasets"
          }
          retry={() => query.refetch()}
        />
      ) : datasets.length === 0 ? (
        <EmptyState
          title="No datasets yet"
          description="Create a materialized, exportable dataset — directly from raw rows or resolved from a project's research query."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {datasets.map((dataset) => (
            <DatasetCard
              key={dataset.dataset_id}
              dataset={dataset}
              onOpen={() => {
                setSelected(dataset);
                setSelectedTab("quality");
              }}
              onDelete={() => del.mutate(dataset.dataset_id)}
            />
          ))}
        </div>
      )}

      <DatasetBuilder
        open={builderOpen}
        onOpenChange={setBuilderOpen}
        onCreated={() => {
          void queryClient.invalidateQueries({ queryKey: ["datasets"] });
        }}
      />

      <Dialog
        open={selected !== null}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      >
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{selected?.name}</DialogTitle>
            <DialogDescription className="font-mono text-xs">
              {selected?.dataset_id}
            </DialogDescription>
          </DialogHeader>

          {selected ? (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{selected.entity_type}</Badge>
                <Badge variant="secondary">
                  {selected.member_count.toLocaleString()} members
                </Badge>
                {selected.overflow ? (
                  <Badge variant="destructive">chunked storage</Badge>
                ) : null}
                <a
                  href={getDatasetExportUrl(selected.dataset_id, "csv")}
                  download
                  className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs font-medium outline-none hover:bg-muted focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                >
                  <Download className="size-3.5" aria-hidden />
                  CSV
                </a>
                <a
                  href={getDatasetExportUrl(selected.dataset_id, "json")}
                  download
                  className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs font-medium outline-none hover:bg-muted focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                >
                  <Download className="size-3.5" aria-hidden />
                  JSON
                </a>
              </div>

              <p className="text-xs text-muted-foreground">
                created {formatDateTime(selected.created_at)}
              </p>

              <Tabs
                value={selectedTab}
                onValueChange={(value) => setSelectedTab(value as "quality" | "members")}
              >
                <TabsList>
                  <TabsTrigger value="quality">Quality</TabsTrigger>
                  <TabsTrigger value="members">Members</TabsTrigger>
                </TabsList>
                <TabsContent value="quality" className="mt-4">
                  <QualityPanel datasetId={selected.dataset_id} />
                </TabsContent>
                <TabsContent value="members" className="mt-4">
                  <MemberList datasetId={selected.dataset_id} />
                </TabsContent>
              </Tabs>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function DatasetCard({
  dataset,
  onOpen,
  onDelete,
}: {
  dataset: Dataset;
  onOpen: () => void;
  onDelete: () => void;
}) {
  return (
    <Card className="flex flex-col gap-2 p-4">
      <div className="flex items-start justify-between gap-2">
        <button
          type="button"
          onClick={onOpen}
          className="text-left text-sm font-medium outline-none hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50"
        >
          {dataset.name}
        </button>
        <Button type="button" variant="ghost" size="icon-sm" aria-label={`Delete dataset ${dataset.name}`} onClick={onDelete}>
          <Trash2 className="size-4" aria-hidden />
        </Button>
      </div>
      <div className="flex flex-wrap gap-1">
        <Badge variant="outline">{dataset.entity_type}</Badge>
        <Badge variant="secondary">
          {dataset.member_count.toLocaleString()} members
        </Badge>
      </div>
      <p className="text-xs text-muted-foreground">
        {formatDateTime(dataset.created_at)}
      </p>
      {dataset.description ? (
        <p className="line-clamp-2 text-xs text-muted-foreground">
          {dataset.description}
        </p>
      ) : null}
    </Card>
  );
}

function MemberList({ datasetId }: { datasetId: string }) {
  const query = useQuery({
    queryKey: ["datasets", datasetId, "members"],
    queryFn: async () => {
      const first = await getDatasetMembers(datasetId);
      const rest: Paginated<Record<string, unknown>>[] = [];
      let cursor = first.next_cursor;
      while (cursor && rest.length < 10) {
        const next = await getDatasetMembers(datasetId, cursor);
        rest.push(next);
        cursor = next.next_cursor;
      }
      return { first, rest };
    },
  });

  const members = query.data
    ? [
        ...query.data.first.items,
        ...query.data.rest.flatMap((page) => page.items),
      ]
    : [];

  const idField = "id";

  return (
    <div className="max-h-80 overflow-auto rounded-md border">
      {query.isLoading ? (
        <LoadingState label="Loading members…" />
      ) : members.length === 0 ? (
        <EmptyState title="No members" description="This dataset has no member rows." />
      ) : (
        <Table aria-label="Dataset members">
          <TableHeader>
            <TableRow>
              <TableHead>#</TableHead>
              <TableHead>Member</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {members.map((member, index) => {
              const key = member[idField] ?? index;
              return (
                <TableRow key={String(key)}>
                  <TableCell className="text-right tabular-nums text-muted-foreground">
                    {index + 1}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {JSON.stringify(member)}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

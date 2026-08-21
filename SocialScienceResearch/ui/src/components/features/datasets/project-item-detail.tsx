"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Trash2, X, FolderKanban, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState, ErrorState, LoadingState } from "@/components/features/state";
import {
  useProjectItem,
  useUpdateProjectItem,
  useDeleteProjectItem,
  useAddSamplesToItem,
  useRemoveSamplesFromItem,
  useAddDatasetsToItem,
  useRemoveDatasetsFromItem,
  useDatasetList,
} from "@/services/queries";
import { useSampleList } from "@/services/samples";
import { useToast } from "@/components/ui/toast";
import { formatDateTime } from "@/lib/format";
import type { ProjectItem, ProjectItemType } from "@/lib/dataset-types";

const ITEM_TYPES: { value: ProjectItemType; label: string }[] = [
  { value: "sample_group", label: "Sample group" },
  { value: "dataset_group", label: "Dataset group" },
  { value: "mixed", label: "Mixed" },
];

export function ProjectItemDetail({
  projectId,
  itemId,
}: {
  projectId: string;
  itemId: string;
}) {
  const { toast } = useToast();
  const router = useRouter();
  const [addSamplesOpen, setAddSamplesOpen] = useState(false);
  const [addDatasetsOpen, setAddDatasetsOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);

  const itemQuery = useProjectItem(projectId, itemId);
  const datasetsQuery = useDatasetList();
  const datasetNames = new Map(
    (datasetsQuery.data?.pages ?? [])
      .flatMap((p) => p.items)
      .filter((d) => d.name)
      .map((d) => [d.dataset_id, d.name]),
  );
  const deleteItem = useDeleteProjectItem();
  const removeSamples = useRemoveSamplesFromItem();
  const removeDatasets = useRemoveDatasetsFromItem();

  function handleDelete() {
    if (!itemQuery.data) return;
    if (!confirm(`Delete item "${itemQuery.data.name}"?`)) return;
    deleteItem.mutate(
      { projectId, itemId },
      {
        onSuccess: () => {
          toast({ title: "Project item deleted" });
          router.push(`/projects/${projectId}`);
        },
        onError: (error) => {
          toast({
            variant: "destructive",
            title: "Could not delete item",
            description: error instanceof Error ? error.message : "Unknown error",
          });
        },
      },
    );
  }

  if (itemQuery.isLoading) return <LoadingState label="Loading item…" />;
  if (itemQuery.isError)
    return (
      <ErrorState
        message={
          itemQuery.error instanceof Error
            ? itemQuery.error.message
            : "Failed to load item"
        }
        detail="This project item may not exist."
      />
    );
  const item = itemQuery.data!;

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <FolderKanban className="size-5 text-muted-foreground" aria-hidden />
          {item.name}
        </h1>
        {item.description ? (
          <p className="text-sm text-muted-foreground">{item.description}</p>
        ) : null}
      </header>

      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline">{item.item_type}</Badge>
        {item.tags.map((tag) => (
          <Badge key={tag} variant="secondary">
            {tag}
          </Badge>
        ))}
        <span className="ml-auto text-xs text-muted-foreground">
          updated {formatDateTime(item.updated_at)}
        </span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setEditOpen(true)}
        >
          <Pencil className="size-4" aria-hidden />
          Edit
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="text-destructive"
          onClick={handleDelete}
          disabled={deleteItem.isPending}
        >
          <Trash2 className="size-4" aria-hidden />
          Delete
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <Card className="p-3">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Samples
            </p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-6 text-xs"
              onClick={() => setAddSamplesOpen(true)}
            >
              <Plus className="size-3" aria-hidden />
              Add
            </Button>
          </div>
          {item.sample_ids.length > 0 ? (
            <ul className="mt-2 space-y-1">
              {item.sample_ids.map((sampleId) => (
                <li
                  key={sampleId}
                  className="flex items-center justify-between gap-2 rounded bg-muted/30 px-2 py-1"
                >
                  <button
                    type="button"
                    onClick={() => router.push("/samples")}
                    className="truncate font-mono text-xs text-primary underline-offset-2 hover:underline"
                  >
                    {sampleId}
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      removeSamples.mutate({ projectId, itemId, sampleIds: [sampleId] })
                    }
                    aria-label={`Remove sample ${sampleId}`}
                    className="text-muted-foreground outline-none hover:text-destructive focus-visible:ring-1 focus-visible:ring-ring"
                  >
                    <X className="size-3" aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-xs text-muted-foreground">
              No samples in this item.
            </p>
          )}
        </Card>

        <Card className="p-3">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Datasets
            </p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-6 text-xs"
              onClick={() => setAddDatasetsOpen(true)}
            >
              <Plus className="size-3" aria-hidden />
              Add
            </Button>
          </div>
          {item.dataset_ids.length > 0 ? (
            <ul className="mt-2 space-y-1">
              {item.dataset_ids.map((datasetId) => (
                <li
                  key={datasetId}
                  className="flex items-center justify-between gap-2 rounded bg-muted/30 px-2 py-1"
                >
                  <button
                    type="button"
                    onClick={() => router.push("/datasets")}
                    className="truncate text-xs text-primary underline-offset-2 hover:underline"
                  >
                    {datasetNames.get(datasetId) ?? datasetId}
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      removeDatasets.mutate({ projectId, itemId, datasetIds: [datasetId] })
                    }
                    aria-label={`Remove dataset ${datasetId}`}
                    className="text-muted-foreground outline-none hover:text-destructive focus-visible:ring-1 focus-visible:ring-ring"
                  >
                    <X className="size-3" aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-xs text-muted-foreground">
              No datasets in this item.
            </p>
          )}
        </Card>
      </div>

      <AddSamplesDialog
        open={addSamplesOpen}
        onOpenChange={setAddSamplesOpen}
        projectId={projectId}
        itemId={itemId}
        existingIds={item.sample_ids}
      />
      <AddDatasetsDialog
        open={addDatasetsOpen}
        onOpenChange={setAddDatasetsOpen}
        projectId={projectId}
        itemId={itemId}
        existingIds={item.dataset_ids}
      />
      <EditItemDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        projectId={projectId}
        item={item}
      />
    </div>
  );
}

function EditItemDialog({
  open,
  onOpenChange,
  projectId,
  item,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  item: ProjectItem;
}) {
  const { toast } = useToast();
  const [name, setName] = useState(item.name);
  const [description, setDescription] = useState(item.description ?? "");
  const [itemType, setItemType] = useState<ProjectItemType>(item.item_type);
  const [tags, setTags] = useState(item.tags.join(", "));

  const updateItem = useUpdateProjectItem();
  const isPending = updateItem.isPending;

  function handleOpenChange(next: boolean) {
    if (!next) onOpenChange(false);
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      toast({
        variant: "destructive",
        title: "Name required",
        description: "Give the project item a name.",
      });
      return;
    }

    updateItem.mutate(
      {
        projectId,
        itemId: item.item_id,
        patch: {
          name: name.trim(),
          description: description.trim() || undefined,
          item_type: itemType,
          tags: tags
            .split(",")
            .map((part) => part.trim())
            .filter(Boolean),
        },
      },
      {
        onSuccess: () => {
          toast({ title: "Project item updated" });
          onOpenChange(false);
        },
        onError: (error) => {
          toast({
            variant: "destructive",
            title: "Could not update project item",
            description: error instanceof Error ? error.message : "Unknown error",
          });
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Edit project item</DialogTitle>
          <DialogDescription>Update the item details.</DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Field label="Name">
            <Input
              id="project-item-edit-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              autoComplete="off"
              required
            />
          </Field>

          <Field label="Description">
            <Textarea
              id="project-item-edit-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={2}
            />
          </Field>

          <Field label="Item type">
            <Select
              value={itemType}
              onValueChange={(value) =>
                setItemType((value ?? "sample_group") as ProjectItemType)
              }
              items={ITEM_TYPES.map((t) => ({ value: t.value, label: t.label }))}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ITEM_TYPES.map((type) => (
                  <SelectItem key={type.value} value={type.value}>
                    {type.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>

          <Field label="Tags (comma separated)">
            <Input
              id="project-item-edit-tags"
              value={tags}
              onChange={(event) => setTags(event.target.value)}
              autoComplete="off"
            />
          </Field>

          <DialogFooter showCloseButton>
            <Button type="submit" disabled={isPending}>
              {isPending ? "Saving…" : "Save changes"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </Label>
      {children}
    </div>
  );
}

function AddSamplesDialog({
  open,
  onOpenChange,
  projectId,
  itemId,
  existingIds,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  itemId: string;
  existingIds: string[];
}) {
  const { toast } = useToast();
  const samplesQuery = useSampleList();
  const addSamples = useAddSamplesToItem();

  const samples = samplesQuery.data?.pages.flatMap((p) => p.items) ?? [];
  const existing = new Set(existingIds);
  const available = samples.filter((s) => !existing.has(s.sample_id));

  function handleAdd(sampleId: string) {
    addSamples.mutate(
      { projectId, itemId, sampleIds: [sampleId] },
      {
        onSuccess: () => {
          toast({ title: "Sample added" });
          onOpenChange(false);
        },
        onError: (error) => {
          toast({
            variant: "destructive",
            title: "Could not add sample",
            description: error instanceof Error ? error.message : "Unknown error",
          });
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add sample to item</DialogTitle>
          <DialogDescription>Select a sample to add to this item.</DialogDescription>
        </DialogHeader>

        {samplesQuery.isLoading ? (
          <LoadingState label="Loading samples…" />
        ) : available.length === 0 ? (
          <EmptyState
            title="No samples available"
            description="All samples are already in this item or no samples exist."
          />
        ) : (
          <div className="max-h-64 space-y-1 overflow-y-auto">
            {available.map((sample) => (
              <label
                key={sample.sample_id}
                className="flex cursor-pointer items-center gap-3 rounded-md border px-3 py-2 hover:bg-muted"
              >
                <input
                  type="radio"
                  name="sample"
                  onChange={() => handleAdd(sample.sample_id)}
                  disabled={addSamples.isPending}
                  className="size-4"
                />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-mono text-sm">{sample.sample_id}</p>
                  <p className="text-xs text-muted-foreground">
                    {sample.entity_type} · {sample.strategy}
                  </p>
                </div>
              </label>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function AddDatasetsDialog({
  open,
  onOpenChange,
  projectId,
  itemId,
  existingIds,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  itemId: string;
  existingIds: string[];
}) {
  const { toast } = useToast();
  const datasetsQuery = useDatasetList();
  const addDatasets = useAddDatasetsToItem();

  const datasets = datasetsQuery.data?.pages.flatMap((p) => p.items) ?? [];
  const existing = new Set(existingIds);
  const available = datasets.filter((d) => !existing.has(d.dataset_id));

  function handleAdd(datasetId: string) {
    addDatasets.mutate(
      { projectId, itemId, datasetIds: [datasetId] },
      {
        onSuccess: () => {
          toast({ title: "Dataset added" });
          onOpenChange(false);
        },
        onError: (error) => {
          toast({
            variant: "destructive",
            title: "Could not add dataset",
            description: error instanceof Error ? error.message : "Unknown error",
          });
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add dataset to item</DialogTitle>
          <DialogDescription>Select a dataset to add to this item.</DialogDescription>
        </DialogHeader>

        {datasetsQuery.isLoading ? (
          <LoadingState label="Loading datasets…" />
        ) : available.length === 0 ? (
          <EmptyState
            title="No datasets available"
            description="All datasets are already in this item or no datasets exist."
          />
        ) : (
          <div className="max-h-64 space-y-1 overflow-y-auto">
            {available.map((dataset) => (
              <label
                key={dataset.dataset_id}
                className="flex cursor-pointer items-center gap-3 rounded-md border px-3 py-2 hover:bg-muted"
              >
                <input
                  type="radio"
                  name="dataset"
                  onChange={() => handleAdd(dataset.dataset_id)}
                  disabled={addDatasets.isPending}
                  className="size-4"
                />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{dataset.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {dataset.member_count.toLocaleString()} members ·{" "}
                    {dataset.entity_type}
                  </p>
                </div>
              </label>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
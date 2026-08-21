"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Trash2, FolderKanban } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "@/components/features/state";
import { ProjectItemBuilder } from "@/components/features/datasets/project-item-builder";
import { ProjectExportButton } from "@/components/features/export-tab";
import { useProject, useProjectItems, useDeleteProjectItem } from "@/services/queries";
import { useToast } from "@/components/ui/toast";
import { formatDateTime } from "@/lib/format";
import type { ProjectItem } from "@/lib/dataset-types";

export function ProjectDetail({ projectId }: { projectId: string }) {
  const { toast } = useToast();
  const router = useRouter();
  const [builderOpen, setBuilderOpen] = useState(false);

  const projectQuery = useProject(projectId);
  const itemsQuery = useProjectItems(projectId);
  const deleteItem = useDeleteProjectItem();

  function handleDeleteItem(item: ProjectItem) {
    if (!confirm(`Delete item "${item.name}"?`)) return;
    deleteItem.mutate(
      { projectId, itemId: item.item_id },
      {
        onSuccess: () => {
          toast({ title: "Project item deleted" });
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

  if (projectQuery.isLoading) return <LoadingState label="Loading project…" />;
  if (projectQuery.isError)
    return (
      <ErrorState
        message={
          projectQuery.error instanceof Error
            ? projectQuery.error.message
            : "Failed to load project"
        }
        detail="This project may not exist."
      />
    );
  const project = projectQuery.data!;
  const items = itemsQuery.data?.items ?? [];

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <FolderKanban className="size-5 text-muted-foreground" aria-hidden />
          {project.name}
        </h1>
        {project.description ? (
          <p className="text-sm text-muted-foreground">{project.description}</p>
        ) : null}
      </header>

      <div className="flex flex-wrap items-center gap-2">
        <ProjectExportButton projectId={projectId} />
        <Button variant="outline" size="sm" onClick={() => router.push("/network/full")}>
          Open Network Lab
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field
          label="Notes"
          value={<span className="whitespace-pre-wrap">{project.notes ?? "—"}</span>}
        />
        <Field
          label="Variables"
          value={
            project.variable_selection.length > 0 ? (
              <code>{project.variable_selection.join(", ")}</code>
            ) : (
              "—"
            )
          }
        />
        <Field
          label="Config hash"
          value={<code className="break-all">{project.config_hash}</code>}
        />
        <Field
          label="Updated"
          value={<span className="font-mono">{formatDateTime(project.updated_at)}</span>}
        />
      </div>

      <Card className="p-3">
        <p className="mb-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
          Targets
        </p>
        {project.targets.length > 0 ? (
          <ul className="space-y-1">
            {project.targets.map((target, index) => (
              <li key={index} className="flex items-center gap-2 text-sm">
                <Badge variant="outline">{target.kind}</Badge>
                <code className="truncate">{target.url}</code>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No collection targets.</p>
        )}
      </Card>

      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium">
          {itemsQuery.isLoading
            ? "Project items"
            : `${items.length} project items`}
        </h2>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setBuilderOpen(true)}
        >
          <Plus className="size-4" aria-hidden />
          New item
        </Button>
      </div>

      {itemsQuery.isLoading ? (
        <LoadingState label="Loading items…" />
      ) : itemsQuery.isError ? (
        <ErrorState
          message={
            itemsQuery.error instanceof Error
              ? itemsQuery.error.message
              : "Failed to load items"
          }
          retry={() => itemsQuery.refetch()}
        />
      ) : items.length === 0 ? (
        <EmptyState
          title="No items yet"
          description="Create project items — sample groups, dataset groups or mixed collections — to organize the sources behind a research design."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {items.map((item) => (
            <ProjectItemCard
              key={item.item_id}
              item={item}
              onOpen={() =>
                router.push(`/projects/${projectId}/items/${item.item_id}`)
              }
              onDelete={() => handleDeleteItem(item)}
            />
          ))}
        </div>
      )}

      <ProjectItemBuilder
        projectId={projectId}
        open={builderOpen}
        onOpenChange={setBuilderOpen}
        onCreated={(item) =>
          router.push(`/projects/${projectId}/items/${item.item_id}`)
        }
      />
    </div>
  );
}

function ProjectItemCard({
  item,
  onOpen,
  onDelete,
}: {
  item: ProjectItem;
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
          {item.name}
        </button>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label={`Delete item ${item.name}`}
          onClick={onDelete}
        >
          <Trash2 className="size-4" aria-hidden />
        </Button>
      </div>

      <div className="flex flex-wrap gap-1">
        <Badge variant="outline">{item.item_type}</Badge>
        <Badge variant="secondary">{item.sample_ids.length} samples</Badge>
        <Badge variant="secondary">{item.dataset_ids.length} datasets</Badge>
      </div>

      {item.tags.length > 0 ? (
        <div className="flex flex-wrap gap-1">
          {item.tags.map((tag) => (
            <Badge key={tag} variant="outline">
              {tag}
            </Badge>
          ))}
        </div>
      ) : null}

      <p className="text-xs text-muted-foreground">
        updated {formatDateTime(item.updated_at)}
      </p>
    </Card>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Card className="p-3">
      <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <div className="mt-0.5 text-sm">{value}</div>
    </Card>
  );
}
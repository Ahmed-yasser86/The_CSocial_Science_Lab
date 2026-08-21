"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus, Trash2, ChevronDown, ChevronRight, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/toast";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState, ErrorState, LoadingState } from "@/components/features/state";
import { formatDateTime } from "@/lib/format";
import {
  useProjectList,
  useCreateProject,
  useUpdateProject,
  useDeleteProject,
  useAddDatasetToProject,
  useRemoveDatasetFromProject,
  useDatasetList,
} from "@/services/queries";
import type { Project } from "@/lib/dataset-types";

export function ProjectManager() {
  const [builderOpen, setBuilderOpen] = useState(false);
  const [editProject, setEditProject] = useState<Project | null>(null);
  const [expandedProjects, setExpandedProjects] = useState<Set<string>>(new Set());
  const [addDatasetTo, setAddDatasetTo] = useState<Project | null>(null);

  const projectsQuery = useProjectList();
  const projects = projectsQuery.data?.pages.flatMap((p) => p.items) ?? [];

  function toggleExpanded(projectId: string) {
    setExpandedProjects((prev) => {
      const next = new Set(prev);
      if (next.has(projectId)) {
        next.delete(projectId);
      } else {
        next.add(projectId);
      }
      return next;
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {projectsQuery.isLoading
            ? "Loading…"
            : `${projects.length} projects`}
        </p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setBuilderOpen(true)}
        >
          <Plus className="size-4" aria-hidden />
          New project
        </Button>
      </div>

      {projectsQuery.isLoading ? (
        <LoadingState label="Loading projects…" />
      ) : projectsQuery.isError ? (
        <ErrorState
          message={
            projectsQuery.error instanceof Error
              ? projectsQuery.error.message
              : "Failed to load projects"
          }
          retry={() => projectsQuery.refetch()}
        />
      ) : projects.length === 0 ? (
        <EmptyState
          title="No projects yet"
          description="Create a research project to organize datasets and track collection targets."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {projects.map((project) => (
            <ProjectCard
              key={project.project_id}
              project={project}
              expanded={expandedProjects.has(project.project_id)}
              onToggleExpand={() => toggleExpanded(project.project_id)}
              onEdit={() => setEditProject(project)}
              onAddDataset={() => setAddDatasetTo(project)}
              onDeleteSuccess={() => void projectsQuery.refetch()}
            />
          ))}
        </div>
      )}

      <ProjectBuilder
        open={builderOpen || editProject !== null}
        onOpenChange={(open) => {
          if (!open) {
            setBuilderOpen(false);
            setEditProject(null);
          }
        }}
        onCreated={() => {
          void projectsQuery.refetch();
        }}
        editProject={editProject}
      />

      {addDatasetTo && (
        <AddDatasetDialog
          open={addDatasetTo !== null}
          onOpenChange={(open) => {
            if (!open) setAddDatasetTo(null);
          }}
          project={addDatasetTo}
          onAdded={() => void projectsQuery.refetch()}
        />
      )}
    </div>
  );
}

function ProjectCard({
  project,
  expanded,
  onToggleExpand,
  onEdit,
  onAddDataset,
  onDeleteSuccess,
}: {
  project: Project;
  expanded: boolean;
  onToggleExpand: () => void;
  onEdit: () => void;
  onAddDataset: () => void;
  onDeleteSuccess: () => void;
}) {
  const { toast } = useToast();
  const deleteProject = useDeleteProject();
  const removeDataset = useRemoveDatasetFromProject();
  const datasetsQuery = useDatasetList();
  const datasetNames = new Map(
    (datasetsQuery.data?.pages ?? [])
      .flatMap((p) => p.items)
      .filter((d) => d.name)
      .map((d) => [d.dataset_id, d.name]),
  );

  function handleDelete() {
    if (!confirm(`Delete project "${project.name}"?`)) return;
    deleteProject.mutate(project.project_id, {
      onSuccess: () => {
        toast({ title: "Project deleted" });
        onDeleteSuccess();
      },
      onError: (error) => {
        toast({
          variant: "destructive",
          title: "Could not delete project",
          description: error instanceof Error ? error.message : "Unknown error",
        });
      },
    });
  }

  function handleRemoveDataset(datasetId: string) {
    removeDataset.mutate(
      { projectId: project.project_id, datasetId },
      {
        onError: (error) => {
          toast({
            variant: "destructive",
            title: "Could not remove dataset",
            description: error instanceof Error ? error.message : "Unknown error",
          });
        },
      }
    );
  }

  return (
    <Card className="flex flex-col gap-2 p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <button
            type="button"
            onClick={onToggleExpand}
            className="outline-none hover:text-foreground focus-visible:ring-1 focus-visible:ring-ring"
            aria-label={expanded ? "Collapse" : "Expand"}
          >
            {expanded ? (
              <ChevronDown className="size-4" aria-hidden />
            ) : (
              <ChevronRight className="size-4" aria-hidden />
            )}
          </button>
          <div className="min-w-0">
            <Link
              href={`/projects/${project.project_id}`}
              className="block truncate text-sm font-medium outline-none hover:underline focus-visible:ring-1 focus-visible:ring-ring"
            >
              {project.name}
            </Link>
            <p className="text-xs text-muted-foreground">
              {formatDateTime(project.created_at)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label={`Edit project ${project.name}`}
            onClick={onEdit}
          >
            <span className="sr-only">Edit</span>
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label={`Delete project ${project.name}`}
            onClick={handleDelete}
            disabled={deleteProject.isPending}
          >
            <Trash2 className="size-4" aria-hidden />
          </Button>
        </div>
      </div>

      {project.description && (
        <p className="text-xs text-muted-foreground line-clamp-2">
          {project.description}
        </p>
      )}

      <div className="flex flex-wrap gap-1">
        {project.targets.slice(0, 3).map((target, i) => (
          <Badge key={i} variant="outline" className="text-[10px]">
            {target.kind}
          </Badge>
        ))}
        {project.targets.length > 3 && (
          <Badge variant="outline" className="text-[10px]">
            +{project.targets.length - 3}
          </Badge>
        )}
      </div>

      {expanded && (
        <div className="mt-2 space-y-2 border-t pt-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium">Datasets</span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onAddDataset}
              className="h-6 text-xs"
            >
              <Plus className="size-3" aria-hidden />
              Add
            </Button>
          </div>
          {project.dataset_ids && project.dataset_ids.length > 0 ? (
            <div className="space-y-1">
              {project.dataset_ids.map((datasetId) => (
                <div
                  key={datasetId}
                  className="flex items-center justify-between gap-2 rounded bg-muted/30 px-2 py-1"
                >
                  <span className="text-xs truncate">
                    {datasetNames.get(datasetId) ?? datasetId}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleRemoveDataset(datasetId)}
                    className="text-muted-foreground outline-none hover:text-destructive focus-visible:ring-1 focus-visible:ring-ring"
                    aria-label={`Remove dataset ${datasetId}`}
                  >
                    <X className="size-3" aria-hidden />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              No datasets in this project.
            </p>
          )}
        </div>
      )}
    </Card>
  );
}

function ProjectBuilder({
  open,
  onOpenChange,
  onCreated,
  editProject,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: () => void;
  editProject?: Project | null;
}) {
  const { toast } = useToast();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [notes, setNotes] = useState("");
  const [variableSelection, setVariableSelection] = useState("");

  const createProject = useCreateProject();
  const updateProject = useUpdateProject();

  const isEditing = !!editProject;
  const isPending = createProject.isPending || updateProject.isPending;

  function reset() {
    setName("");
    setDescription("");
    setNotes("");
    setVariableSelection("");
  }

  function handleOpenChange(next: boolean) {
    if (!next) reset();
    onOpenChange(next);
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      toast({
        variant: "destructive",
        title: "Name required",
        description: "Provide a name for the project.",
      });
      return;
    }

    const variables = variableSelection
      .split(",")
      .map((v) => v.trim())
      .filter(Boolean);

    if (isEditing && editProject) {
      updateProject.mutate(
        {
          projectId: editProject.project_id,
          patch: {
            name: name.trim(),
            description: description.trim() || undefined,
            notes: notes.trim() || undefined,
            variable_selection: variables,
          },
        },
        {
          onSuccess: () => {
            toast({ title: "Project updated" });
            onCreated?.();
            handleOpenChange(false);
          },
          onError: (error) => {
            toast({
              variant: "destructive",
              title: "Could not update project",
              description: error instanceof Error ? error.message : "Unknown error",
            });
          },
        }
      );
    } else {
      createProject.mutate(
        {
          name: name.trim(),
          description: description.trim() || undefined,
          notes: notes.trim() || undefined,
          targets: [],
          variable_selection: variables,
        },
        {
          onSuccess: () => {
            toast({ title: "Project created" });
            onCreated?.();
            handleOpenChange(false);
          },
          onError: (error) => {
            toast({
              variant: "destructive",
              title: "Could not create project",
              description: error instanceof Error ? error.message : "Unknown error",
            });
          },
        }
      );
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {isEditing ? "Edit project" : "New research project"}
          </DialogTitle>
          <DialogDescription>
            {isEditing
              ? "Update the project details."
              : "Create a new research project to organize your data collection."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Field label="Name">
            <Input
              id="project-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g. 2026 recommendation study"
              autoComplete="off"
              required
            />
          </Field>

          <Field label="Description">
            <Textarea
              id="project-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="What this project investigates…"
              rows={2}
            />
          </Field>

          <Field label="Notes">
            <Textarea
              id="project-notes"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              placeholder="Methodological notes…"
              rows={2}
            />
          </Field>

          <Field label="Variable selection (comma separated)">
            <Input
              id="project-variables"
              value={variableSelection}
              onChange={(event) => setVariableSelection(event.target.value)}
              placeholder="views, likes, comment_count"
              autoComplete="off"
            />
          </Field>

          <DialogFooter showCloseButton>
            <Button type="submit" disabled={isPending}>
              {isPending ? (
                <>Creating…</>
              ) : (
                <>{isEditing ? "Update project" : "Create project"}</>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function AddDatasetDialog({
  open,
  onOpenChange,
  project,
  onAdded,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  project: Project | null;
  onAdded?: () => void;
}) {
  const { toast } = useToast();
  const datasetsQuery = useDatasetList();
  const addDataset = useAddDatasetToProject();

  const datasets = datasetsQuery.data?.pages.flatMap((p) => p.items) ?? [];
  const existingDatasetIds = new Set(project?.dataset_ids || []);

  const availableDatasets = datasets.filter(
    (d) => !existingDatasetIds.has(d.dataset_id)
  );

  function handleAdd(datasetId: string) {
    if (!project) return;
    addDataset.mutate(
      { projectId: project.project_id, datasetId },
      {
        onSuccess: () => {
          toast({ title: "Dataset added to project" });
          onAdded?.();
          onOpenChange(false);
        },
        onError: (error) => {
          toast({
            variant: "destructive",
            title: "Could not add dataset",
            description: error instanceof Error ? error.message : "Unknown error",
          });
        },
      }
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add dataset to project</DialogTitle>
          <DialogDescription>
            Select a dataset to add to{" "}
            <span className="font-medium">{project?.name}</span>.
          </DialogDescription>
        </DialogHeader>

        {datasetsQuery.isLoading ? (
          <LoadingState label="Loading datasets…" />
        ) : availableDatasets.length === 0 ? (
          <EmptyState
            title="No datasets available"
            description="All datasets are already in this project or no datasets exist."
          />
        ) : (
          <div className="max-h-64 overflow-y-auto space-y-1">
            {availableDatasets.map((dataset) => (
              <label
                key={dataset.dataset_id}
                className="flex items-center gap-3 rounded-md border px-3 py-2 hover:bg-muted cursor-pointer"
              >
                <input
                  type="radio"
                  name="dataset"
                  onChange={() => handleAdd(dataset.dataset_id)}
                  disabled={addDataset.isPending}
                  className="size-4"
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{dataset.name}</p>
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

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </Label>
      {children}
    </div>
  );
}
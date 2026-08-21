"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, Trash2, ChevronDown, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "@/components/features/state";
import { ProjectBuilder } from "@/components/features/datasets/project-builder";
import { listProjects, deleteProject } from "@/services/datasets";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useToast } from "@/components/ui/toast";
import { formatDateTime } from "@/lib/format";
import type { ResearchProject } from "@/lib/dataset-types";

export default function ProjectsPage() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const router = useRouter();
  const [builderOpen, setBuilderOpen] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["projects"],
    queryFn: () => listProjects(),
  });

  const del = useMutation({
    mutationFn: (projectId: string) => deleteProject(projectId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast({ title: "Project deleted" });
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Could not delete project",
        description: error instanceof Error ? error.message : "Unknown error",
      });
    },
  });

  const projects = query.data?.items ?? [];

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <Plus className="size-5 text-muted-foreground" aria-hidden />
          Projects
        </h1>
        <p className="text-sm text-muted-foreground">
          Persisted research-project designs: collection targets, variable
          selection and notes. Datasets can be materialized directly from a
          project&apos;s research query.
        </p>
      </header>

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {query.data?.total !== null && query.data?.total !== undefined
            ? `${query.data.total.toLocaleString()} projects`
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

      {query.isLoading ? (
        <LoadingState label="Loading projects…" />
      ) : query.isError ? (
        <ErrorState
          message={
            query.error instanceof Error
              ? query.error.message
              : "Failed to load projects"
          }
          retry={() => query.refetch()}
        />
      ) : projects.length === 0 ? (
        <EmptyState
          title="No projects yet"
          description="Persist a research design to make it auditable and re-runnable."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {projects.map((project) => (
            <ProjectCard
              key={project.project_id}
              project={project}
              expanded={expanded === project.project_id}
              onToggle={() =>
                setExpanded((prev) =>
                  prev === project.project_id ? null : project.project_id,
                )
              }
              onDelete={() => del.mutate(project.project_id)}
            />
          ))}
        </div>
      )}

      <ProjectBuilder
        open={builderOpen}
        onOpenChange={setBuilderOpen}
        onCreated={(project) => {
          void queryClient.invalidateQueries({ queryKey: ["projects"] });
          router.push(`/projects/${project.project_id}`);
        }}
      />
    </div>
  );
}

function ProjectCard({
  project,
  expanded,
  onToggle,
  onDelete,
}: {
  project: ResearchProject;
  expanded: boolean;
  onToggle: () => void;
  onDelete: () => void;
}) {
  return (
    <Card className="flex flex-col gap-2 p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-1">
          <button
            type="button"
            onClick={onToggle}
            aria-label={expanded ? "Collapse" : "Expand"}
            className="shrink-0 rounded-md p-0.5 text-muted-foreground outline-none hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
          >
            {expanded ? (
              <ChevronDown className="size-4" aria-hidden />
            ) : (
              <ChevronRight className="size-4" aria-hidden />
            )}
          </button>
          <Link
            href={`/projects/${project.project_id}`}
            className="truncate text-sm font-medium outline-none hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50"
          >
            {project.name}
          </Link>
        </div>
        <Button type="button" variant="ghost" size="icon-sm" aria-label={`Delete project ${project.name}`} onClick={onDelete}>
          <Trash2 className="size-4" aria-hidden />
        </Button>
      </div>

      <div className="flex flex-wrap gap-1">
        {project.targets.map((target, index) => (
          <Badge key={index} variant="outline">
            {target.kind}
          </Badge>
        ))}
        {project.variable_selection && project.variable_selection.length > 0 ? (
          <Badge variant="secondary">
            {project.variable_selection.length} variables
          </Badge>
        ) : null}
      </div>

      <p className="text-xs text-muted-foreground">
        updated {formatDateTime(project.updated_at)}
      </p>

      {expanded ? (
        <div className="space-y-2 text-xs">
          {project.description ? (
            <p className="text-muted-foreground">{project.description}</p>
          ) : null}
          <div>
            <p className="mb-1 font-medium text-muted-foreground">Targets</p>
            <ul className="space-y-0.5">
              {project.targets.map((target, index) => (
                <li key={index} className="flex items-center gap-2">
                  <Badge variant="outline">{target.kind}</Badge>
                  <code className="truncate">{target.url}</code>
                </li>
              ))}
            </ul>
          </div>
          {project.variable_selection &&
          project.variable_selection.length > 0 ? (
            <div>
              <p className="mb-1 font-medium text-muted-foreground">Variables</p>
              <p className="font-mono">{project.variable_selection.join(", ")}</p>
            </div>
          ) : null}
          <div>
            <p className="mb-1 font-medium text-muted-foreground">Config hash</p>
            <code className="break-all">{project.config_hash}</code>
          </div>
        </div>
      ) : null}
    </Card>
  );
}

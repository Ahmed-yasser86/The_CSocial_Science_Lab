"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, Plus } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { getJobs } from "@/services/api";
import { listProjects, createDataset, getChannels, getRuns } from "@/services/datasets";
import { useResearchVariables } from "@/services/queries";
import type {
  CreateDatasetInput,
  Dataset,
  DatasetEntityType,
  ResearchProject,
  Channel,
} from "@/lib/dataset-types";
import type { QueryGroup, CollectionRun } from "@/lib/types";
import { ErrorState } from "@/components/features/state";
import { CriteriaFilterBar } from "@/components/features/criteria-filter-bar";
import {
  Tabs,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Combobox } from "@/components/ui/combobox";

const ENTITY_TYPE_OPTIONS: { value: DatasetEntityType; label: string }[] = [
  { value: "video", label: "Video" },
  { value: "comment", label: "Comment" },
  { value: "channel", label: "Channel" },
  { value: "recommendation", label: "Recommendation" },
  { value: "author", label: "Author" },
];

const SOURCE_OPTIONS = [
  { value: "raw", label: "Whole corpus" },
  { value: "project", label: "From project" },
  { value: "scope", label: "By runs/channels/videos" },
] as const;

const SCOPE_MODES = [
  { value: "runs", label: "Runs" },
  { value: "jobs", label: "Jobs" },
  { value: "channels", label: "Channels" },
  { value: "videos", label: "Videos" },
] as const;

export function DatasetBuilder({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (dataset: Dataset) => void;
}) {
  const { toast } = useToast();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [entityType, setEntityType] =
    useState<DatasetEntityType>("video");
  const [sourceMode, setSourceMode] = useState<"project" | "raw" | "scope">("raw");
  const [projectId, setProjectId] = useState("");
  const [includeRaw, setIncludeRaw] = useState(false);
  const [scopeMode, setScopeMode] = useState<"runs" | "jobs" | "channels" | "videos">("runs");
  const [selectedRunIds, setSelectedRunIds] = useState<string[]>([]);
  const [selectedJobIds, setSelectedJobIds] = useState<string[]>([]);
  const [selectedChannelIds, setSelectedChannelIds] = useState<string[]>([]);
  const [selectedVideoIds, setSelectedVideoIds] = useState<string[]>([]);
  const [criteriaGroup, setCriteriaGroup] = useState<QueryGroup | null>(null);
  const [variableSelection, setVariableSelection] = useState<string[]>([]);

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => listProjects(),
  });

  const projects = projectsQuery.data?.items ?? [];
  const projectsLoading = projectsQuery.isLoading;

  const runsQuery = useQuery({
    queryKey: ["runs", "all"],
    queryFn: () => getRuns(),
    enabled: sourceMode === "scope" && scopeMode === "runs",
  });

  const jobsQuery = useQuery({
    queryKey: ["jobs", "list"],
    queryFn: () => getJobs(),
    enabled: sourceMode === "scope" && scopeMode === "jobs",
  });

  const channelsQuery = useQuery({
    queryKey: ["channels"],
    queryFn: () => getChannels(),
    enabled: sourceMode === "scope" && scopeMode === "channels",
  });

  const variablesQuery = useResearchVariables(entityType);
  const availableVariables = variablesQuery.data ?? [];

  const create = useMutation({
    mutationFn: () => {
      const body: CreateDatasetInput = {
        name: name.trim(),
        entity_type: entityType,
        include_raw: includeRaw,
      };
      if (description.trim()) body.description = description.trim();
      if (sourceMode === "project" && projectId) body.project_id = projectId;
      if (sourceMode === "scope") {
        if (scopeMode === "runs" && selectedRunIds.length) body.run_ids = selectedRunIds;
        if (scopeMode === "jobs" && selectedJobIds.length) body.job_ids = selectedJobIds;
        if (scopeMode === "channels" && selectedChannelIds.length) body.channel_ids = selectedChannelIds;
        if (scopeMode === "videos" && selectedVideoIds.length) body.video_ids = selectedVideoIds;
        if (criteriaGroup) body.criteria = criteriaGroup;
        if (variableSelection.length) body.variable_selection = variableSelection;
      }
      return createDataset(body);
    },
    onSuccess: (dataset) => {
      toast({
        title: "Dataset created",
        description: `${dataset.name} · ${dataset.entity_type}`,
      });
      onCreated(dataset);
      reset();
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Could not create dataset",
        description:
          error instanceof Error ? error.message : "Unknown error",
      });
    },
  });

  function reset() {
    setName("");
    setDescription("");
    setEntityType("video");
    setSourceMode("raw");
    setProjectId("");
    setIncludeRaw(false);
    setScopeMode("runs");
    setSelectedRunIds([]);
    setSelectedChannelIds([]);
    setSelectedVideoIds([]);
    setCriteriaGroup(null);
    setVariableSelection([]);
  }

  function handleOpenChange(next: boolean) {
    if (!next) reset();
    onOpenChange(next);
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim() || create.isPending) return;
    if (sourceMode === "project" && !projectId) {
      toast({
        variant: "destructive",
        title: "Select a project",
        description: "Choose the project the dataset should be built from.",
      });
      return;
    }
    if (sourceMode === "scope") {
      if (scopeMode === "runs" && selectedRunIds.length === 0) {
        toast({
          variant: "destructive",
          title: "Select at least one run",
          description: "Choose runs to include in the dataset.",
        });
        return;
      }
      if (scopeMode === "channels" && selectedChannelIds.length === 0) {
        toast({
          variant: "destructive",
          title: "Select at least one channel",
          description: "Choose channels to include in the dataset.",
        });
        return;
      }
      if (scopeMode === "videos" && selectedVideoIds.length === 0) {
        toast({
          variant: "destructive",
          title: "Select at least one video",
          description: "Choose videos to include in the dataset.",
        });
        return;
      }
    }
    create.mutate();
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>New dataset</DialogTitle>
          <DialogDescription>
            Create an exportable research dataset — either directly from raw
            rows or resolved from an existing project.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="space-y-4">
          <Field label="Name">
            <Input
              id="dataset-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g. 2026 comments sample"
              autoComplete="off"
              required
            />
          </Field>

          <Field label="Description">
            <Textarea
              id="dataset-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="What this dataset captures…"
            />
          </Field>

          <Field label="Entity type">
            <Select
              value={entityType}
              onValueChange={(value) =>
                setEntityType((value ?? "video") as DatasetEntityType)
              }
              items={ENTITY_TYPE_OPTIONS}
            >
              <SelectTrigger id="dataset-entity-type" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="w-[--anchor-width]">
                {ENTITY_TYPE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>

          <Field label="Source">
            <div className="flex flex-wrap gap-2">
              {SOURCE_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setSourceMode(option.value)}
                  aria-pressed={sourceMode === option.value}
                  className="rounded-md border border-border px-3 py-1 text-xs font-medium outline-none hover:bg-muted focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-pressed:bg-primary aria-pressed:text-primary-foreground"
                >
                  {option.label}
                </button>
              ))}
            </div>
          </Field>

          {sourceMode === "project" ? (
            <Field label="Source project">
              {projectsQuery.isError ? (
                <ErrorState
                  message={
                    projectsQuery.error instanceof Error
                      ? projectsQuery.error.message
                      : "Failed to load projects"
                  }
                  retry={() => projectsQuery.refetch()}
                />
              ) : (
                <Select
                  value={projectId}
                  onValueChange={(value) => setProjectId(value ?? "")}
                  items={projects.map((project: ResearchProject) => ({
                    value: project.project_id,
                    label: project.name,
                  }))}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select project…" />
                  </SelectTrigger>
                  <SelectContent className="w-[--anchor-width]">
                    {projects.map((project: ResearchProject) => (
                      <SelectItem
                        key={project.project_id}
                        value={project.project_id}
                      >
                        {project.name}
                      </SelectItem>
                    ))}
                    {!projectsLoading && projects.length === 0 ? (
                      <p className="px-2 py-2 text-xs text-muted-foreground">
                        No projects yet — create one on the Projects page.
                      </p>
                    ) : null}
                  </SelectContent>
                </Select>
              )}
            </Field>
          ) : sourceMode === "scope" ? (
            <>
              <Field label="Scope type">
                <Tabs
                  value={scopeMode}
                  onValueChange={(value) => setScopeMode(value as "runs" | "jobs" | "channels" | "videos")}
                  className="w-full"
                >
                  <TabsList className="grid w-full grid-cols-3">
                    {SCOPE_MODES.map((mode) => (
                      <TabsTrigger key={mode.value} value={mode.value}>
                        {mode.label}
                      </TabsTrigger>
                    ))}
                  </TabsList>
                </Tabs>
              </Field>

              {scopeMode === "runs" && (
                <Field label="Select runs">
                  {runsQuery.isLoading ? (
                    <div className="text-xs text-muted-foreground">Loading runs…</div>
                  ) : runsQuery.isError ? (
                    <ErrorState
                      message={
                        runsQuery.error instanceof Error
                          ? runsQuery.error.message
                          : "Failed to load runs"
                      }
                      retry={() => runsQuery.refetch()}
                    />
                  ) : (
                    <div className="max-h-60 overflow-auto space-y-1 rounded-md border bg-muted/20 p-2">
                      {runsQuery.data?.length === 0 ? (
                        <p className="text-xs text-muted-foreground">No runs found.</p>
                      ) : (
                        runsQuery.data?.map((run: CollectionRun) => (
                          <label
                            key={run.run_id}
                            className="flex items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-muted cursor-pointer"
                          >
                            <input
                              type="checkbox"
                              checked={selectedRunIds.includes(run.run_id)}
                              onChange={(e) =>
                                setSelectedRunIds((prev) =>
                                  e.target.checked
                                    ? [...prev, run.run_id]
                                    : prev.filter((id) => id !== run.run_id)
                                )
                              }
                              className="size-4"
                            />
                            <span className="font-mono text-xs truncate">{run.run_id}</span>
                            <Badge variant="outline" className="text-[10px]">
                              {run.status}
                            </Badge>
                            <span className="text-xs text-muted-foreground ml-auto">
                              {new Date(run.started_at).toLocaleDateString()}
                            </span>
                          </label>
                        ))
                      )}
                    </div>
                  )}
                  {selectedRunIds.length > 0 && (
                    <p className="text-xs text-muted-foreground">
                      {selectedRunIds.length} run(s) selected
                    </p>
                  )}
                </Field>
              )}

              {scopeMode === "jobs" && (
                <Field label="Select jobs">
                  {jobsQuery.isLoading ? (
                    <div className="text-xs text-muted-foreground">Loading jobs�</div>
                  ) : jobsQuery.isError ? (
                    <ErrorState
                      message={
                        jobsQuery.error instanceof Error
                          ? jobsQuery.error.message
                          : "Failed to load jobs"
                      }
                      retry={() => jobsQuery.refetch()}
                    />
                  ) : (
                    <div className="max-h-60 overflow-auto space-y-1 rounded-md border bg-muted/20 p-2">
                      {jobsQuery.data?.length === 0 ? (
                        <p className="text-xs text-muted-foreground">No jobs found.</p>
                      ) : (
                        jobsQuery.data?.map((job) => (
                          <label
                            key={job.job_id}
                            className="flex items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-muted cursor-pointer"
                          >
                            <input
                              type="checkbox"
                              checked={selectedJobIds.includes(job.job_id)}
                              onChange={(e) =>
                                setSelectedJobIds((prev) =>
                                  e.target.checked
                                    ? [...prev, job.job_id]
                                    : prev.filter((id) => id !== job.job_id)
                                )
                              }
                              className="size-4"
                            />
                            <span className="font-mono text-xs truncate">{job.job_id}</span>
                            <Badge variant="outline" className="text-[10px]">
                              {job.status}
                            </Badge>
                          </label>
                        ))
                      )}
                    </div>
                  )}
                  {selectedJobIds.length > 0 && (
                    <p className="text-xs text-muted-foreground">
                      {selectedJobIds.length} job(s) selected � every run under
                      the selected jobs is included.
                    </p>
                  )}
                </Field>
              )}
              {scopeMode === "channels" && (
                <Field label="Select channels">
                  {channelsQuery.isLoading ? (
                    <div className="text-xs text-muted-foreground">Loading channels…</div>
                  ) : channelsQuery.isError ? (
                    <ErrorState
                      message={
                        channelsQuery.error instanceof Error
                          ? channelsQuery.error.message
                          : "Failed to load channels"
                      }
                      retry={() => channelsQuery.refetch()}
                    />
                  ) : (
                    <div className="max-h-60 overflow-auto space-y-1 rounded-md border bg-muted/20 p-2">
                      {channelsQuery.data?.items.length === 0 ? (
                        <p className="text-xs text-muted-foreground">No channels found.</p>
                      ) : (
                        channelsQuery.data?.items.map((channel: Channel) => (
                          <label
                            key={channel.channel_id}
                            className="flex items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-muted cursor-pointer"
                          >
                            <input
                              type="checkbox"
                              checked={selectedChannelIds.includes(channel.channel_id)}
                              onChange={(e) =>
                                setSelectedChannelIds((prev) =>
                                  e.target.checked
                                    ? [...prev, channel.channel_id]
                                    : prev.filter((id) => id !== channel.channel_id)
                                )
                              }
                              className="size-4"
                            />
                            <span className="font-mono text-xs truncate">{channel.channel_id}</span>
                            <span className="text-xs text-muted-foreground ml-auto truncate max-w-[200px]">
                              {channel.title ?? "—"}
                            </span>
                          </label>
                        ))
                      )}
                    </div>
                  )}
                  {selectedChannelIds.length > 0 && (
                    <p className="text-xs text-muted-foreground">
                      {selectedChannelIds.length} channel(s) selected
                    </p>
                  )}
                </Field>
              )}

              {scopeMode === "videos" && (
                <Field label="Select videos">
                  <div className="max-h-60 overflow-auto space-y-1 rounded-md border bg-muted/20 p-2">
                    <p className="text-xs text-muted-foreground">
                      Video selection by channel coming soon. For now, use runs or channels scope.
                    </p>
                  </div>
                  {selectedVideoIds.length > 0 && (
                    <p className="text-xs text-muted-foreground">
                      {selectedVideoIds.length} video(s) selected
                    </p>
                  )}
                </Field>
              )}

              <Field label="Criteria filters">
                <CriteriaFilterBar
                  entity={entityType}
                  onChange={setCriteriaGroup}
                />
              </Field>

              <Field label="Variable selection">
                {availableVariables.length > 0 ? (
                  <Combobox
                    items={availableVariables.map((v) => ({
                      value: v.name,
                      label: `${v.name} (${v.data_type})`,
                    }))}
                    value={variableSelection}
                    onChange={(value) => setVariableSelection(Array.isArray(value) ? value : [value])}
                    placeholder="Select variables…"
                    multiple
                    searchPlaceholder="Search variables…"
                  />
                ) : (
                  <p className="text-xs text-muted-foreground">
                    No variables available for this entity type.
                  </p>
                )}
                {variableSelection.length > 0 && (
                  <p className="text-xs text-muted-foreground">
                    {variableSelection.length} variable(s) selected
                  </p>
                )}
              </Field>
            </>
          ) : null}

          <div className="flex items-center gap-2">
            <Checkbox
              id="dataset-include-raw"
              checked={includeRaw}
              onCheckedChange={(value) => setIncludeRaw(value === true)}
            />
            <Label htmlFor="dataset-include-raw">
              Include raw fields alongside projected variables
            </Label>
          </div>

          <DialogFooter showCloseButton>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? (
                <>
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                  Creating…
                </>
              ) : (
                <>
                  <Plus className="size-4" aria-hidden />
                  Create dataset
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
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
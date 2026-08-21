"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2 } from "lucide-react";
import { listProjects, createProject } from "@/services/datasets";
import { request } from "@/services/api";
import type { Project } from "@/lib/dataset-types";

export interface AddToProjectDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  nodeIds: string[];
  runId?: string;
  onSaved?: (itemId: string) => void;
}

export function AddToProjectDialog({ open, onOpenChange, nodeIds, runId, onSaved }: AddToProjectDialogProps) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<string>("");
  const [newProjectName, setNewProjectName] = useState<string>("");
  const [format, setFormat] = useState<string>("xlsx");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ensureProjects() {
    if (projects.length > 0) return;
    try {
      const page = await listProjects();
      setProjects(page.items ?? []);
    } catch {
      setProjects([]);
    }
  }

  async function handleSave() {
    setLoading(true);
    setError(null);
    try {
      let target = projectId;
      if (!target) {
        if (!newProjectName.trim()) {
          setError("Pick an existing project or enter a name for a new one.");
          setLoading(false);
          return;
        }
        const created = await createProject({ name: newProjectName.trim(), description: "Auto-created from filtered network nodes", targets: [], variable_selection: [] });
        target = created.project_id;
        setProjects((prev) => [...prev, created]);
      }
      const item = await request<{ item_id: string }>("/network/export-to-project", {
        method: "POST",
        body: JSON.stringify({
          project_id: target,
          format,
          run_id: runId ?? null,
          video_ids: nodeIds,
          name: `Filtered network · ${nodeIds.length} nodes · ${format.toUpperCase()}`,
          description: `Exported ${nodeIds.length} filtered network nodes (${format}) to the project.`,
        }),
      });
      onSaved?.(item.item_id);
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save to project");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add filtered network to project</DialogTitle>
          <DialogDescription>
            Save the currently filtered {nodeIds.length} node{nodeIds.length === 1 ? "" : "s"} as a
            project artifact (with its edges).
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="add-to-project-format" className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Format
            </Label>
            <Select value={format} onValueChange={(v) => setFormat(v ?? "xlsx")}>
              <SelectTrigger id="add-to-project-format" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="xlsx">Excel (.xlsx)</SelectItem>
                <SelectItem value="csv">CSV</SelectItem>
                <SelectItem value="graphml">GraphML</SelectItem>
                <SelectItem value="json">JSON</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Project
            </Label>
            <Select value={projectId} onValueChange={(v) => { setProjectId(v ?? ""); setNewProjectName(""); }}>
              <SelectTrigger className="w-full" onClick={() => void ensureProjects()}>
                <SelectValue placeholder="Select a project…" />
              </SelectTrigger>
              <SelectContent>
                {projects.length === 0 ? (
                  <SelectItem value="" disabled>
                    No projects yet
                  </SelectItem>
                ) : null}
                {projects.map((p) => (
                  <SelectItem key={p.project_id} value={p.project_id}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="new-project-name" className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              …or create a new project
            </Label>
            <Input
              id="new-project-name"
              value={newProjectName}
              onChange={(e) => { setNewProjectName(e.target.value); if (e.target.value) setProjectId(""); }}
              placeholder="New project name"
              disabled={!!projectId}
            />
          </div>

          {error ? <p className="text-sm text-destructive">{error}</p> : null}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>
            Cancel
          </Button>
          <Button onClick={() => void handleSave()} disabled={loading}>
            {loading ? <Loader2 className="animate-spin" aria-hidden /> : null}
            Save to project
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
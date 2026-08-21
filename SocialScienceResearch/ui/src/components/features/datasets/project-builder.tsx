"use client";

import { useState } from "react";
import { Loader2, Plus, X } from "lucide-react";
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
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { createProject } from "@/services/datasets";
import type {
  CreateProjectInput,
  ProjectTarget,
  ProjectTargetKind,
  ResearchProject,
} from "@/lib/dataset-types";

const TARGET_KINDS: { value: ProjectTargetKind; label: string }[] = [
  { value: "channel", label: "Channel" },
  { value: "video", label: "Video" },
  { value: "recommendation", label: "Recommendation" },
];

export function ProjectBuilder({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: (project: ResearchProject) => void;
}) {
  const { toast } = useToast();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [notes, setNotes] = useState("");
  const [targets, setTargets] = useState<ProjectTarget[]>([]);
  const [targetKind, setTargetKind] = useState<ProjectTargetKind>("channel");
  const [targetUrl, setTargetUrl] = useState("");
  const [variables, setVariables] = useState("");
  const [creating, setCreating] = useState(false);

  function reset() {
    setName("");
    setDescription("");
    setNotes("");
    setTargets([]);
    setTargetKind("channel");
    setTargetUrl("");
    setVariables("");
  }

  function handleOpenChange(next: boolean) {
    if (!next) reset();
    onOpenChange(next);
  }

  function addTarget() {
    const url = targetUrl.trim();
    if (!url) return;
    setTargets((prev) => [...prev, { kind: targetKind, url }]);
    setTargetUrl("");
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      toast({
        variant: "destructive",
        title: "Name required",
        description: "Give the project a name.",
      });
      return;
    }
    if (targets.length === 0) {
      toast({
        variant: "destructive",
        title: "No targets",
        description: "Add at least one collection target.",
      });
      return;
    }
    const body: CreateProjectInput = {
      name: name.trim(),
      targets,
      variable_selection: variables
        .split(",")
        .map((part) => part.trim())
        .filter(Boolean),
    };
    if (description.trim()) body.description = description.trim();
    if (notes.trim()) body.notes = notes.trim();

    setCreating(true);
    try {
      const created = await createProject(body);
      toast({ title: "Project saved", description: name.trim() });
      onCreated?.(created);
      onOpenChange(false);
    } catch (error) {
      toast({
        variant: "destructive",
        title: "Could not save project",
        description: error instanceof Error ? error.message : "Unknown error",
      });
    } finally {
      setCreating(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>New research project</DialogTitle>
          <DialogDescription>
            Persist a research design — collection targets, variable selection
            and notes — so it can be re-run and reproduced.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="space-y-4">
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
            />
          </Field>

          <div className="space-y-2">
            <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Targets
            </Label>
            {targets.length > 0 ? (
              <ul className="space-y-1">
                {targets.map((target, index) => (
                  <li
                    key={`${target.kind}-${target.url}-${index}`}
                    className="flex items-center justify-between gap-2 rounded-md border bg-muted/20 px-3 py-1.5 text-sm"
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      <Badge variant="outline">{target.kind}</Badge>
                      <code className="truncate text-xs">{target.url}</code>
                    </span>
                    <button
                      type="button"
                      aria-label={`Remove target ${target.url}`}
                      onClick={() =>
                        setTargets((prev) => prev.filter((_, i) => i !== index))
                      }
                      className="text-muted-foreground outline-none hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
                    >
                      <X className="size-3.5" aria-hidden />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-muted-foreground">
                No targets yet — add at least one channel, video or
                recommendation target.
              </p>
            )}

            <div className="flex flex-wrap items-center gap-2">
              <Select
                value={targetKind}
                onValueChange={(value) =>
                  setTargetKind((value ?? "channel") as ProjectTargetKind)
                }
                items={TARGET_KINDS.map((k) => ({ value: k.value, label: k.label }))}
              >
                <SelectTrigger className="w-36">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TARGET_KINDS.map((kind) => (
                    <SelectItem key={kind.value} value={kind.value}>
                      {kind.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Input
                value={targetUrl}
                onChange={(event) => setTargetUrl(event.target.value)}
                placeholder="https://…"
                className="min-w-56 flex-1"
                autoComplete="off"
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    addTarget();
                  }
                }}
              />
              <Button type="button" variant="outline" size="sm" onClick={addTarget}>
                <Plus className="size-3.5" aria-hidden />
                Add
              </Button>
            </div>
          </div>

          <Field label="Variable selection (comma separated)">
            <Input
              id="project-variables"
              value={variables}
              onChange={(event) => setVariables(event.target.value)}
              placeholder="views, likes, comment_count"
              autoComplete="off"
            />
          </Field>

          <Field label="Notes">
            <Textarea
              id="project-notes"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              placeholder="Methodological notes…"
              rows={3}
            />
          </Field>

          <DialogFooter showCloseButton>
            <Button type="submit" disabled={creating}>
              {creating ? (
                <>
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                  Saving…
                </>
              ) : (
                <>
                  <Plus className="size-4" aria-hidden />
                  Save project
                </>
              )}
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

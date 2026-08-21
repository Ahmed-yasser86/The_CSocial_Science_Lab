"use client";

import { useState } from "react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { useCreateProjectItem } from "@/services/queries";
import type { ProjectItem, ProjectItemType } from "@/lib/dataset-types";

const ITEM_TYPES: { value: ProjectItemType; label: string }[] = [
  { value: "sample_group", label: "Sample group" },
  { value: "dataset_group", label: "Dataset group" },
  { value: "mixed", label: "Mixed" },
];

export function ProjectItemBuilder({
  projectId,
  open,
  onOpenChange,
  onCreated,
}: {
  projectId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: (item: ProjectItem) => void;
}) {
  const { toast } = useToast();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [itemType, setItemType] = useState<ProjectItemType>("sample_group");
  const [tags, setTags] = useState("");

  const createItem = useCreateProjectItem();
  const isPending = createItem.isPending;

  function reset() {
    setName("");
    setDescription("");
    setItemType("sample_group");
    setTags("");
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
        description: "Give the project item a name.",
      });
      return;
    }

    createItem.mutate(
      {
        projectId,
        body: {
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
        onSuccess: (item) => {
          toast({ title: "Project item created" });
          onCreated?.(item);
          handleOpenChange(false);
        },
        onError: (error) => {
          toast({
            variant: "destructive",
            title: "Could not create project item",
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
          <DialogTitle>New project item</DialogTitle>
          <DialogDescription>
            Group the samples and datasets behind a research design into a
            named, auditable item.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Field label="Name">
            <Input
              id="project-item-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g. Channel sample group"
              autoComplete="off"
              required
            />
          </Field>

          <Field label="Description">
            <Textarea
              id="project-item-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="What this item collects…"
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
              id="project-item-tags"
              value={tags}
              onChange={(event) => setTags(event.target.value)}
              placeholder="yt, comment"
              autoComplete="off"
            />
          </Field>

          <DialogFooter showCloseButton>
            <Button type="submit" disabled={isPending}>
              {isPending ? "Creating…" : "Create item"}
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
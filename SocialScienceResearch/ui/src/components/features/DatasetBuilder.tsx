"use client";

import { useState, useMemo } from "react";
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
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { useSampleList } from "@/services/samples";
import { useCombineDatasets } from "@/services/queries";
import type { SampleLabels, Dataset } from "@/lib/dataset-types";
import type { Sample } from "@/lib/sample-types";

export function DatasetBuilder({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: (dataset: Dataset) => void;
}) {
  const { toast } = useToast();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedSampleIds, setSelectedSampleIds] = useState<string[]>([]);
  const [deduplicate, setDeduplicate] = useState(false);
  const [preserveLineage, setPreserveLineage] = useState(false);
  const [labels, setLabels] = useState<SampleLabels>({});
  const [newLabelKey, setNewLabelKey] = useState("");
  const [newLabelValue, setNewLabelValue] = useState("");
  const [customLabelKey, setCustomLabelKey] = useState("");
  const [customLabelValue, setCustomLabelValue] = useState("");

  const samplesQuery = useSampleList();
  const combine = useCombineDatasets();

  const samples = useMemo(() => {
    if (!samplesQuery.data) return [];
    return samplesQuery.data.pages.flatMap((page) => page.items);
  }, [samplesQuery.data]);

  const totalMembers = useMemo(() => {
    return samples
      .filter((s) => selectedSampleIds.includes(s.sample_id))
      .reduce((acc, s) => acc + s.sample_size, 0);
  }, [samples, selectedSampleIds]);

  function reset() {
    setName("");
    setDescription("");
    setSelectedSampleIds([]);
    setDeduplicate(false);
    setPreserveLineage(false);
    setLabels({});
    setNewLabelKey("");
    setNewLabelValue("");
    setCustomLabelKey("");
    setCustomLabelValue("");
  }

  function handleOpenChange(next: boolean) {
    if (!next) reset();
    onOpenChange(next);
  }

  function toggleSample(sampleId: string) {
    setSelectedSampleIds((prev) =>
      prev.includes(sampleId)
        ? prev.filter((id) => id !== sampleId)
        : [...prev, sampleId]
    );
  }

  function addSystemLabel() {
    if (!newLabelKey.trim()) return;
    setLabels((prev) => ({
      ...prev,
      system: { ...prev.system, [newLabelKey.trim()]: newLabelValue.trim() },
    }));
    setNewLabelKey("");
    setNewLabelValue("");
  }

  function addResearchLabel() {
    if (!newLabelKey.trim()) return;
    setLabels((prev) => ({
      ...prev,
      research: { ...prev.research, [newLabelKey.trim()]: newLabelValue.trim() },
    }));
    setNewLabelKey("");
    setNewLabelValue("");
  }

  function addCustomLabel() {
    if (!customLabelKey.trim()) return;
    setLabels((prev) => ({
      ...prev,
      custom: { ...prev.custom, [customLabelKey.trim()]: customLabelValue.trim() },
    }));
    setCustomLabelKey("");
    setCustomLabelValue("");
  }

  function removeLabel(category: keyof SampleLabels, key: string) {
    setLabels((prev) => {
      const updated = { ...prev };
      if (updated[category]) {
        const filtered = { ...updated[category] };
        delete filtered[key];
        if (Object.keys(filtered).length === 0) {
          delete updated[category];
        } else {
          updated[category] = filtered;
        }
      }
      return updated;
    });
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      toast({
        variant: "destructive",
        title: "Name required",
        description: "Provide a name for the dataset.",
      });
      return;
    }
    if (selectedSampleIds.length === 0) {
      toast({
        variant: "destructive",
        title: "No samples selected",
        description: "Select at least one sample to combine.",
      });
      return;
    }
    combine.mutate(
      {
        name: name.trim(),
        description: description.trim() || undefined,
        sample_ids: selectedSampleIds,
        deduplicate,
        preserve_lineage: preserveLineage,
        labels: Object.keys(labels).length > 0 ? labels : undefined,
      },
      {
        onSuccess: (dataset) => {
          toast({
            title: "Dataset created",
            description: `${dataset.name} · ${dataset.member_count.toLocaleString()} members`,
          });
          onCreated?.(dataset);
          handleOpenChange(false);
        },
        onError: (error) => {
          toast({
            variant: "destructive",
            title: "Could not create dataset",
            description: error instanceof Error ? error.message : "Unknown error",
          });
        },
      }
    );
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Combine samples into dataset</DialogTitle>
          <DialogDescription>
            Merge multiple samples into a single dataset with optional deduplication
            and custom labels.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="space-y-4">
          <Field label="Name">
            <Input
              id="dataset-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g. Combined video sample Q1 2026"
              autoComplete="off"
              required
            />
          </Field>

          <Field label="Description">
            <Textarea
              id="dataset-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="What this combined dataset represents…"
              rows={2}
            />
          </Field>

          <Field label="Select samples">
            {samplesQuery.isLoading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" aria-hidden />
                Loading samples…
              </div>
            ) : samplesQuery.isError ? (
              <p className="text-sm text-destructive">
                Failed to load samples:{" "}
                {samplesQuery.error instanceof Error
                  ? samplesQuery.error.message
                  : "Unknown error"}
              </p>
            ) : samples.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No samples available. Create samples first.
              </p>
            ) : (
              <div className="max-h-48 overflow-y-auto space-y-1 rounded-md border bg-muted/20 p-2">
                {samples.map((sample: Sample) => (
                  <label
                    key={sample.sample_id}
                    className="flex items-center gap-3 rounded px-2 py-1.5 text-sm hover:bg-muted cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedSampleIds.includes(sample.sample_id)}
                      onChange={() => toggleSample(sample.sample_id)}
                      className="size-4"
                    />
                    <span className="font-mono text-xs truncate flex-1">
                      {sample.sample_id}
                    </span>
                    <Badge variant="outline" className="text-[10px]">
                      {sample.entity_type}
                    </Badge>
                    <Badge variant="secondary" className="text-[10px]">
                      {sample.sample_size.toLocaleString()} members
                    </Badge>
                  </label>
                ))}
              </div>
            )}
            {selectedSampleIds.length > 0 && (
              <p className="text-xs text-muted-foreground">
                {selectedSampleIds.length} sample(s) selected
              </p>
            )}
          </Field>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Checkbox
                id="deduplicate"
                checked={deduplicate}
                onCheckedChange={(value) => setDeduplicate(value === true)}
              />
              <Label htmlFor="deduplicate" className="text-sm font-normal">
                Deduplicate members
              </Label>
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                id="preserve-lineage"
                checked={preserveLineage}
                onCheckedChange={(value) => setPreserveLineage(value === true)}
              />
              <Label htmlFor="preserve-lineage" className="text-sm font-normal">
                Preserve lineage
              </Label>
            </div>
          </div>

          <div className="space-y-3">
            <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Labels
            </Label>

            {Object.entries(labels).some(
              ([, v]) => Object.keys(v || {}).length > 0
            ) && (
              <div className="flex flex-wrap gap-1">
                {Object.entries(labels).map(([category, categoryLabels]) =>
                  Object.entries(
                    (categoryLabels || {}) as Record<string, string>
                  ).map(([key, value]) => (
                    <Badge
                      key={`${category}-${key}`}
                      variant="secondary"
                      className="gap-1"
                    >
                      <span className="text-[10px] opacity-60">{category}</span>
                      <span>{key}</span>
                      <span className="opacity-60">:</span>
                      <span>{value}</span>
                      <button
                        type="button"
                        onClick={() =>
                          removeLabel(category as keyof SampleLabels, key)
                        }
                        className="ml-1 outline-none hover:text-destructive focus-visible:ring-1 focus-visible:ring-ring"
                        aria-label={`Remove ${key} label`}
                      >
                        <X className="size-3" aria-hidden />
                      </button>
                    </Badge>
                  ))
                )}
              </div>
            )}

            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Input
                  value={newLabelKey}
                  onChange={(e) => setNewLabelKey(e.target.value)}
                  placeholder="Key"
                  className="h-7 text-xs"
                />
                <Input
                  value={newLabelValue}
                  onChange={(e) => setNewLabelValue(e.target.value)}
                  placeholder="Value"
                  className="h-7 text-xs flex-1"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={addSystemLabel}
                  className="h-7 text-xs"
                >
                  System
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={addResearchLabel}
                  className="h-7 text-xs"
                >
                  Research
                </Button>
              </div>
              <div className="flex items-center gap-2">
                <Input
                  value={customLabelKey}
                  onChange={(e) => setCustomLabelKey(e.target.value)}
                  placeholder="Custom key"
                  className="h-7 text-xs"
                />
                <Input
                  value={customLabelValue}
                  onChange={(e) => setCustomLabelValue(e.target.value)}
                  placeholder="Custom value"
                  className="h-7 text-xs flex-1"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={addCustomLabel}
                  className="h-7 text-xs"
                >
                  Custom
                </Button>
              </div>
            </div>
          </div>

          <div className="rounded-md border bg-muted/30 p-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Preview</span>
              <span className="text-sm tabular-nums">
                {totalMembers.toLocaleString()} total members
                {deduplicate ? " (after dedup)" : ""}
              </span>
            </div>
          </div>

          <DialogFooter showCloseButton>
            <Button type="submit" disabled={combine.isPending}>
              {combine.isPending ? (
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